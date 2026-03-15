#!/bin/bash
# =============================================================
# build-ipk.sh — Build remotbot & luci-app-remotbot IPK files
# Format: gzip'd tar (NOT ar/deb) — standard OpenWrt IPK format
# Usage:  ./scripts/build-ipk.sh [version]
# =============================================================

set -e

VERSION="${1:-1.0.0}"
RELEASE="1"
ARCH="aarch64_cortex-a72"
BUILD_DIR="$(pwd)/.build"
OUTPUT_DIR="$(pwd)/dist"

echo "========================================"
echo " RemotWRT Bot IPK Builder v$VERSION-$RELEASE"
echo "========================================"

mkdir -p "$OUTPUT_DIR"
rm -rf "$BUILD_DIR"

build_ipk() {
    local PKG_NAME="$1"
    local PKG_DESC="$2"
    local DEPENDS="$3"
    local FILES_DIR="$(pwd)/packages/$PKG_NAME/files"

    echo ""
    echo "-> Building $PKG_NAME..."

    local WORK="$BUILD_DIR/$PKG_NAME"
    local DATA_DIR="$WORK/data"
    local CTRL_DIR="$WORK/control"
    mkdir -p "$DATA_DIR" "$CTRL_DIR"

    # Copy source files
    if [ -d "$FILES_DIR" ]; then
        cp -r "$FILES_DIR/." "$DATA_DIR/"
    fi

    # Set permissions inside data tree BEFORE packing
    find "$DATA_DIR" -type d                       -exec chmod 0755 {} \;
    find "$DATA_DIR" -type f                       -exec chmod 0644 {} \;
    find "$DATA_DIR" -type f -name "*.py"          -exec chmod 0755 {} \;
    find "$DATA_DIR/etc/init.d"     -type f        -exec chmod 0755 {} \; 2>/dev/null || true
    find "$DATA_DIR/etc/uci-defaults" -type f      -exec chmod 0755 {} \; 2>/dev/null || true

    local INSTALLED_SIZE
    INSTALLED_SIZE=$(du -sk "$DATA_DIR" 2>/dev/null | cut -f1 || echo "100")

    # control
    cat > "$CTRL_DIR/control" <<EOF
Package: $PKG_NAME
Version: $VERSION-$RELEASE
Architecture: $ARCH
Maintainer: RemotWRT <https://github.com/irfanFRizki/RemotWRT-Bot>
Depends: $DEPENDS
Section: net
Priority: optional
Installed-Size: $INSTALLED_SIZE
Description: $PKG_DESC
EOF

    # conffiles
    if [ -d "$DATA_DIR/etc/config" ]; then
        for f in "$DATA_DIR/etc/config/"*; do
            [ -f "$f" ] && printf "/etc/config/%s\n" "$(basename "$f")"
        done > "$CTRL_DIR/conffiles"
    fi

    # postinst
    if [ "$PKG_NAME" = "remotbot" ]; then
        cat > "$CTRL_DIR/postinst" <<'EOF'
#!/bin/sh
# NOTE: this script runs AFTER opkg extracts data.tar.gz to the filesystem.
# Permissions are already set in the package — do NOT chmod here.
[ -n "${IPKG_INSTROOT}" ] && exit 0

# Enable auto-start
[ -x /etc/init.d/remotbot ] && /etc/init.d/remotbot enable 2>/dev/null || true

# Init UCI config (idempotent — only sets keys that don't exist yet)
if [ -f /etc/config/remotbot ]; then
    uci -q get remotbot.main >/dev/null 2>&1 \
        || uci set remotbot.main=remotbot
    uci -q get remotbot.main.bot_token >/dev/null 2>&1 \
        || uci set remotbot.main.bot_token=''
    uci -q get remotbot.main.allowed_users >/dev/null 2>&1 \
        || uci set remotbot.main.allowed_users=''
    uci -q get remotbot.main.cgi_online_path >/dev/null 2>&1 \
        || uci set remotbot.main.cgi_online_path='/www/cgi-bin/online'
    uci -q get remotbot.main.enabled >/dev/null 2>&1 \
        || uci set remotbot.main.enabled='0'
    uci -q get remotbot.main.log_level >/dev/null 2>&1 \
        || uci set remotbot.main.log_level='INFO'
    uci commit remotbot 2>/dev/null || true
fi

echo ""
echo "==========================="
echo " RemotWRT Bot Installed!"
echo "==========================="
echo ""
echo "Next steps:"
echo "  1. opkg install luci-app-remotbot_*.ipk"
echo "  2. LuCI -> Services -> Remot Bot -> Settings"
echo "  OR via terminal:"
echo "    uci set remotbot.main.bot_token='YOUR_TOKEN'"
echo "    uci set remotbot.main.allowed_users='YOUR_ID'"
echo "    uci set remotbot.main.enabled='1'"
echo "    uci commit remotbot"
echo "    /etc/init.d/remotbot start"
echo ""
exit 0
EOF

    elif [ "$PKG_NAME" = "luci-app-remotbot" ]; then
        cat > "$CTRL_DIR/postinst" <<'EOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
if [ -f /etc/uci-defaults/luci-app-remotbot ]; then
    sh /etc/uci-defaults/luci-app-remotbot \
        && rm -f /etc/uci-defaults/luci-app-remotbot
fi
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache/ 2>/dev/null || true
echo "==========================="
echo " LuCI Remot Bot Installed!"
echo " Go: Services > Remot Bot"
echo "==========================="
exit 0
EOF

    else
        printf '#!/bin/sh\n[ -n "${IPKG_INSTROOT}" ] && exit 0\nexit 0\n' > "$CTRL_DIR/postinst"
    fi
    chmod 0755 "$CTRL_DIR/postinst"

    # prerm
    if [ "$PKG_NAME" = "remotbot" ]; then
        cat > "$CTRL_DIR/prerm" <<'EOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
/etc/init.d/remotbot stop    2>/dev/null || true
/etc/init.d/remotbot disable 2>/dev/null || true
exit 0
EOF
    elif [ "$PKG_NAME" = "luci-app-remotbot" ]; then
        cat > "$CTRL_DIR/prerm" <<'EOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache/ 2>/dev/null || true
exit 0
EOF
    else
        printf '#!/bin/sh\n[ -n "${IPKG_INSTROOT}" ] && exit 0\nexit 0\n' > "$CTRL_DIR/prerm"
    fi
    chmod 0755 "$CTRL_DIR/prerm"

    # Pack data.tar.gz — owner=0:0 (root) to avoid uid/gid issues on device
    echo "  Packing data..."
    tar -czf "$WORK/data.tar.gz" \
        --numeric-owner --owner=0 --group=0 \
        -C "$DATA_DIR" .

    # Pack control.tar.gz
    echo "  Packing control..."
    tar -czf "$WORK/control.tar.gz" \
        --numeric-owner --owner=0 --group=0 \
        -C "$CTRL_DIR" .

    # debian-binary = exactly "2.0\n" (4 bytes)
    printf '2.0\n' > "$WORK/debian-binary"

    # Assemble .ipk = gzip'd tar (OpenWrt format — NOT ar/deb)
    # CRITICAL: bare filenames — opkg matches entry names exactly,
    #           "./debian-binary" != "debian-binary" → silent skip!
    # CRITICAL: data.tar.gz BEFORE control.tar.gz — opkg installs data
    #           first, then runs postinst. Wrong order = postinst runs
    #           before files exist on the filesystem.
    local IPK_NAME="${PKG_NAME}_${VERSION}-${RELEASE}_${ARCH}.ipk"
    echo "  Creating $IPK_NAME..."
    ( cd "$WORK" && tar -czf "$OUTPUT_DIR/$IPK_NAME" \
        --numeric-owner --owner=0 --group=0 \
        debian-binary data.tar.gz control.tar.gz )

    echo "  OK $OUTPUT_DIR/$IPK_NAME"
}

# Build
build_ipk "remotbot" \
    "RemotWRT Telegram Monitoring Bot for OpenWrt / Raspberry Pi 4" \
    "python3, python3-pip"

build_ipk "luci-app-remotbot" \
    "LuCI interface for RemotWRT Telegram Bot (Services > Remot Bot)" \
    "remotbot, luci-base"

# Packages index
echo ""
echo "-> Generating Packages index..."
PACKAGES_FILE="$OUTPUT_DIR/Packages"
: > "$PACKAGES_FILE"
for ipk in "$OUTPUT_DIR"/*.ipk; do
    [ -f "$ipk" ] || continue
    BASENAME=$(basename "$ipk")
    SIZE=$(wc -c < "$ipk")
    MD5=$(md5sum    "$ipk" | cut -d' ' -f1)
    SHA256=$(sha256sum "$ipk" | cut -d' ' -f1)
    IDX=$(mktemp -d)
    tar -xzf "$ipk" -C "$IDX" 2>/dev/null
    tar -xzf "$IDX/control.tar.gz" -C "$IDX" 2>/dev/null || true
    if [ -f "$IDX/control" ]; then
        cat "$IDX/control"         >> "$PACKAGES_FILE"
        echo "Filename: $BASENAME" >> "$PACKAGES_FILE"
        echo "Size: $SIZE"         >> "$PACKAGES_FILE"
        echo "MD5Sum: $MD5"        >> "$PACKAGES_FILE"
        echo "SHA256sum: $SHA256"  >> "$PACKAGES_FILE"
        printf '\n'                >> "$PACKAGES_FILE"
    fi
    rm -rf "$IDX"
done
gzip -9 -k "$PACKAGES_FILE" 2>/dev/null || true

# Summary & verify
echo ""
echo "========================================"
echo " Build Complete!"
echo "========================================"
echo ""
echo "Files:"
ls -lh "$OUTPUT_DIR"/*.ipk
echo ""
echo "Content verification:"
for ipk in "$OUTPUT_DIR"/*.ipk; do
    echo ""
    echo "  [$(basename $ipk)]"
    V=$(mktemp -d)
    tar -xzf "$ipk" -C "$V"
    echo "  IPK members : $(ls $V)"
    echo "  data files  :"
    tar -tzf "$V/data.tar.gz" | grep -v '/$' | sed 's/^/    /'
    echo "  control files:"
    tar -tzf "$V/control.tar.gz" | grep -v '/$' | sed 's/^/    /'
    rm -rf "$V"
done
echo ""
echo "Install order on OpenWrt:"
echo "  1) scp dist/*.ipk root@192.168.7.1:/tmp/"
echo "  2) opkg install /tmp/remotbot_*.ipk"
echo "  3) opkg install /tmp/luci-app-remotbot_*.ipk"
