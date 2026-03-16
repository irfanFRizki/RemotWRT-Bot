#!/bin/bash
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
rm -rf "${BUILD_DIR}"
mkdir -p "${STAGING}/CONTROL" "${STAGING}/usr/share/remotbot" "${STAGING}/usr/bin"
mkdir -p "${STAGING}/etc/init.d" "${STAGING}/etc/config" "${STAGING}/etc/remotbot"
mkdir -p "${STAGING}/usr/lib/lua/luci/controller" "${STAGING}/usr/lib/lua/luci/model/cbi/remotbot"
mkdir -p "${STAGING}/www/luci-static/resources/view/remotbot" "${STAGING}/www/cgi-bin"
mkdir -p "${DIST_DIR}"
cp src/pi4Bot.py                                             "${STAGING}/usr/share/remotbot/pi4Bot.py"
cp src/cgi-bin/online                                        "${STAGING}/www/cgi-bin/online"
cp luci-app-remotbot/root/etc/init.d/remotbot                "${STAGING}/etc/init.d/remotbot"
cp luci-app-remotbot/root/etc/config/remotbot                "${STAGING}/etc/config/remotbot"
cp luci-app-remotbot/root/usr/bin/remotbot-install-deps      "${STAGING}/usr/bin/remotbot-install-deps"
cp luci-app-remotbot/luasrc/controller/remotbot.lua          "${STAGING}/usr/lib/lua/luci/controller/remotbot.lua"
cp luci-app-remotbot/luasrc/model/cbi/remotbot/settings.lua  "${STAGING}/usr/lib/lua/luci/model/cbi/remotbot/settings.lua"
cp luci-app-remotbot/htdocs/luci-static/resources/view/remotbot/dashboard.htm \
                                                             "${STAGING}/www/luci-static/resources/view/remotbot/dashboard.htm"
chmod 755 "${STAGING}/etc/init.d/remotbot" "${STAGING}/usr/bin/remotbot-install-deps"
chmod 755 "${STAGING}/usr/share/remotbot/pi4Bot.py" "${STAGING}/www/cgi-bin/online"
cat > "${STAGING}/etc/remotbot/config.json" << 'JSEOF'
{"bot_token":"","allowed_users":[],"cgi_online_path":"/www/cgi-bin/online","language":"id","cpu_temp_threshold":75,"ram_threshold":85,"wan_timeout_minutes":60,"mac_whitelist":[],"notify_cpu_temp":true,"notify_ram":true,"notify_wan":true,"notify_unknown_device":true}
JSEOF
INSTALLED_SIZE=$(du -sk "${STAGING}" | cut -f1)
cat > "${STAGING}/CONTROL/control" << CTLEOF
Package: ${PKG_NAME}
Version: ${FULL_VERSION}
Depends: luci-base, python3, python3-pip
Source: https://github.com/irfanFRizki/RemotWRT-Bot
Section: luci
Maintainer: irfanFRizki
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Description: LuCI app for RemotWRT Telegram Bot
CTLEOF
cat > "${STAGING}/CONTROL/postinst" << 'PEOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
mkdir -p /etc/remotbot
[ ! -f /etc/remotbot/config.json ] && echo '{"bot_token":"","allowed_users":[],"cgi_online_path":"/www/cgi-bin/online","language":"id","cpu_temp_threshold":75,"ram_threshold":85,"wan_timeout_minutes":60,"mac_whitelist":[],"notify_cpu_temp":true,"notify_ram":true,"notify_wan":true,"notify_unknown_device":true}' > /etc/remotbot/config.json
chmod +x /etc/init.d/remotbot /usr/bin/remotbot-install-deps /usr/share/remotbot/pi4Bot.py /www/cgi-bin/online
/etc/init.d/remotbot enable
rm -rf /tmp/luci-*
sh /usr/bin/remotbot-install-deps > /tmp/remotbot-install.log 2>&1 &
echo "=== RemotWRT Bot Installed === Configure: LuCI > Services > Remot Bot"
exit 0
PEOF
cat > "${STAGING}/CONTROL/prerm" << 'REOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
/etc/init.d/remotbot stop 2>/dev/null; /etc/init.d/remotbot disable 2>/dev/null; exit 0
REOF
chmod 755 "${STAGING}/CONTROL/postinst" "${STAGING}/CONTROL/prerm"
echo "/etc/remotbot/config.json" > "${STAGING}/CONTROL/conffiles"
cd "${STAGING}"; tar czf "${BUILD_DIR}/data.tar.gz" --exclude='./CONTROL' .
cd "${STAGING}/CONTROL"; tar czf "${BUILD_DIR}/control.tar.gz" .
echo "2.0" > "${BUILD_DIR}/debian-binary"
cd "${BUILD_DIR}"; ar r "${DIST_DIR}/${IPK_NAME}" debian-binary control.tar.gz data.tar.gz
rm -rf "${BUILD_DIR}"
echo "=== Build complete ===" && ls -lh "${DIST_DIR}/${IPK_NAME}"
