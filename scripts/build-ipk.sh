#!/bin/bash
# Build IPK package tanpa OpenWrt SDK penuh
# Script ini membuat struktur IPK yang valid secara manual

set -e

PKG_NAME="luci-app-remotbot"
PKG_VERSION=$(grep 'PKG_VERSION:=' Makefile | cut -d= -f2)
PKG_RELEASE=$(grep 'PKG_RELEASE:=' Makefile | cut -d= -f2)
ARCH="all"
FULL_VERSION="${PKG_VERSION}-${PKG_RELEASE}"
IPK_NAME="${PKG_NAME}_${FULL_VERSION}_${ARCH}.ipk"

BUILD_DIR="/tmp/ipk-build-$$"
STAGING="${BUILD_DIR}/staging"
DIST_DIR="$(pwd)/dist"

echo "=== Building ${IPK_NAME} ==="

# Clean & create dirs
rm -rf "${BUILD_DIR}"
mkdir -p "${STAGING}/CONTROL"
mkdir -p "${STAGING}/usr/share/remotbot"
mkdir -p "${STAGING}/etc/init.d"
mkdir -p "${STAGING}/etc/config"
mkdir -p "${STAGING}/etc/remotbot"
mkdir -p "${STAGING}/usr/bin"
mkdir -p "${STAGING}/usr/lib/lua/luci/controller"
mkdir -p "${STAGING}/usr/lib/lua/luci/model/cbi/remotbot"
mkdir -p "${STAGING}/www/luci-static/resources/view/remotbot"
mkdir -p "${DIST_DIR}"

# Copy files
cp src/pi4Bot.py "${STAGING}/usr/share/remotbot/"
cp luci-app-remotbot/root/etc/init.d/remotbot "${STAGING}/etc/init.d/"
cp luci-app-remotbot/root/etc/config/remotbot "${STAGING}/etc/config/"
cp luci-app-remotbot/root/usr/bin/remotbot-install-deps "${STAGING}/usr/bin/"
cp luci-app-remotbot/luasrc/controller/remotbot.lua "${STAGING}/usr/lib/lua/luci/controller/"
cp luci-app-remotbot/luasrc/model/cbi/remotbot/settings.lua "${STAGING}/usr/lib/lua/luci/model/cbi/remotbot/"
cp luci-app-remotbot/htdocs/luci-static/resources/view/remotbot/dashboard.htm "${STAGING}/www/luci-static/resources/view/remotbot/"

# Set permissions
chmod 755 "${STAGING}/etc/init.d/remotbot"
chmod 755 "${STAGING}/usr/bin/remotbot-install-deps"
chmod 755 "${STAGING}/usr/share/remotbot/pi4Bot.py"

# Create default config.json
cat > "${STAGING}/etc/remotbot/config.json" <<'EOF'
{
    "bot_token": "",
    "allowed_users": [],
    "cgi_online_path": "/www/cgi-bin/online"
}
EOF

# Calculate installed size (in KB)
INSTALLED_SIZE=$(du -sk "${STAGING}" | cut -f1)

# Write control file
cat > "${STAGING}/CONTROL/control" <<EOF
Package: ${PKG_NAME}
Version: ${FULL_VERSION}
Depends: luci-base, python3, python3-pip
Source: https://github.com/irfanFRizki/RemotWRT-Bot
Section: luci
Maintainer: irfanFRizki
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Description: LuCI app for RemotWRT Telegram Bot
 OpenWRT Telegram Monitoring Bot for Raspberry Pi 4.
 Provides LuCI menu under Services > Remot Bot with
 Dashboard and Settings for Bot Token and Chat ID configuration.
 Auto-installs Python dependencies on first install.
EOF

# Write postinst
cat > "${STAGING}/CONTROL/postinst" <<'EOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0

mkdir -p /etc/remotbot

if [ ! -f /etc/remotbot/config.json ]; then
    cp /etc/config/remotbot /etc/remotbot/config.json 2>/dev/null || cat > /etc/remotbot/config.json <<'JSONEOF'
{
    "bot_token": "",
    "allowed_users": [],
    "cgi_online_path": "/www/cgi-bin/online"
}
JSONEOF
fi

chmod +x /etc/init.d/remotbot
chmod +x /usr/bin/remotbot-install-deps
chmod +x /usr/share/remotbot/pi4Bot.py

/etc/init.d/remotbot enable

rm -rf /tmp/luci-*

echo ""
echo "=== RemotWRT Bot Installed ==="
echo "Installing Python dependencies in background..."
sh /usr/bin/remotbot-install-deps > /tmp/remotbot-install.log 2>&1 &
echo "Configure: LuCI > Services > Remot Bot > Settings"
echo ""
exit 0
EOF

# Write prerm
cat > "${STAGING}/CONTROL/prerm" <<'EOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
/etc/init.d/remotbot stop 2>/dev/null
/etc/init.d/remotbot disable 2>/dev/null
exit 0
EOF

chmod 755 "${STAGING}/CONTROL/postinst"
chmod 755 "${STAGING}/CONTROL/prerm"

# Build conffiles list
cat > "${STAGING}/CONTROL/conffiles" <<EOF
/etc/remotbot/config.json
EOF

# Create data.tar.gz (everything except CONTROL)
cd "${STAGING}"
find . -not -path './CONTROL*' -not -name '.' | sort > /tmp/ipk-files-$$

# Create tar with proper structure
tar czf "${BUILD_DIR}/data.tar.gz" \
    --exclude='./CONTROL' \
    .

# Create control.tar.gz
cd "${STAGING}/CONTROL"
tar czf "${BUILD_DIR}/control.tar.gz" .

# Create debian-binary
echo "2.0" > "${BUILD_DIR}/debian-binary"

# Pack into IPK (ar archive)
cd "${BUILD_DIR}"
ar r "${DIST_DIR}/${IPK_NAME}" debian-binary control.tar.gz data.tar.gz

# Cleanup
rm -rf "${BUILD_DIR}"
rm -f /tmp/ipk-files-$$

echo ""
echo "=== Build complete ==="
echo "Output: ${DIST_DIR}/${IPK_NAME}"
echo "Size: $(du -sh "${DIST_DIR}/${IPK_NAME}" | cut -f1)"
ls -lh "${DIST_DIR}/${IPK_NAME}"
