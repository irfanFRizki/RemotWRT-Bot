#!/bin/bash
# =============================================================
# build-ipk.sh — Build remotbot and luci-app-remotbot IPK files
# without requiring the full OpenWrt SDK.
# Usage: ./scripts/build-ipk.sh [version]
# =============================================================

set -e

VERSION="${1:-1.0.0}"
RELEASE="1"
ARCH="aarch64_cortex-a72"   # Raspberry Pi 4 architecture
BUILD_DIR="$(pwd)/.build"
OUTPUT_DIR="$(pwd)/dist"

echo "========================================"
echo " RemotWRT Bot IPK Builder"
echo " Version : $VERSION-$RELEASE"
echo " Arch    : $ARCH"
echo "========================================"

mkdir -p "$OUTPUT_DIR"
rm -rf "$BUILD_DIR"

# -------------------------------------------------------
# Helper: build one IPK
# $1 = package name
# $2 = description
# $3 = depends
# $4 = source files dir  (relative to packages/<pkgname>/files)
# $5 = postinst script path (optional)
# $6 = prerm   script path (optional)
# -------------------------------------------------------
build_ipk() {
    local PKG_NAME="$1"
    local PKG_DESC="$2"
    local DEPENDS="$3"
    local FILES_DIR="$(pwd)/packages/$PKG_NAME/files"
    local POSTINST="${5:-}"
    local PRERM="${6:-}"

    echo ""
    echo "→ Building $PKG_NAME..."

    local WORK="$BUILD_DIR/$PKG_NAME"
    local DATA_DIR="$WORK/data"
    local CTRL_DIR="$WORK/control"

    mkdir -p "$DATA_DIR" "$CTRL_DIR"

    # Copy package files into data/
    if [ -d "$FILES_DIR" ]; then
        cp -r "$FILES_DIR/." "$DATA_DIR/"
    fi

    # Fix permissions
    find "$DATA_DIR" -type f -name "*.py"   -exec chmod 755 {} \;
    find "$DATA_DIR" -type f -name "*.sh"   -exec chmod 755 {} \;
    find "$DATA_DIR/etc/init.d" -type f     -exec chmod 755 {} \; 2>/dev/null || true
    find "$DATA_DIR/etc/uci-defaults" -type f -exec chmod 755 {} \; 2>/dev/null || true

    # Calculate installed size (in KB)
    local INSTALLED_SIZE
    INSTALLED_SIZE=$(du -sk "$DATA_DIR" 2>/dev/null | cut -f1 || echo "100")

    # Write control file
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

    # Write conffiles
    local CONFFILES=""
    if [ -d "$DATA_DIR/etc/config" ]; then
        for f in "$DATA_DIR/etc/config/"*; do
            [ -f "$f" ] && CONFFILES="$CONFFILES\n/etc/config/$(basename $f)"
        done
    fi
    if [ -n "$CONFFILES" ]; then
        printf "$CONFFILES\n" > "$CTRL_DIR/conffiles"
    fi

    # Write postinst
    if [ -n "$POSTINST" ] && [ -f "$POSTINST" ]; then
        cp "$POSTINST" "$CTRL_DIR/postinst"
    else
        cat > "$CTRL_DIR/postinst" <<'POSTINST_EOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
POSTINST_EOF
        if [ "$PKG_NAME" = "remotbot" ]; then
            cat >> "$CTRL_DIR/postinst" <<'POSTINST_EOF'
echo "=== RemotWRT Bot Post-Install ==="
chmod +x /usr/bin/pi4Bot.py
chmod +x /etc/init.d/remotbot

# Create default UCI config if missing
if ! uci -q get remotbot.main >/dev/null 2>&1; then
    uci set remotbot.main=remotbot
    uci set remotbot.main.bot_token=''
    uci set remotbot.main.allowed_users=''
    uci set remotbot.main.cgi_online_path='/www/cgi-bin/online'
    uci set remotbot.main.enabled='0'
    uci set remotbot.main.log_level='INFO'
    uci commit remotbot
fi

# Enable service
/etc/init.d/remotbot enable 2>/dev/null || true

echo ""
echo "✓ RemotWRT Bot installed successfully!"
echo ""
echo "Next steps:"
echo "  1. Open LuCI: Services > Remot Bot > Settings"
echo "  2. Enter your Telegram Bot Token"
echo "  3. Enter your Telegram User ID"
echo "  4. Enable the bot and go to Dashboard > Start"
echo ""
echo "Or via UCI:"
echo "  uci set remotbot.main.bot_token='YOUR_TOKEN'"
echo "  uci set remotbot.main.allowed_users='YOUR_USER_ID'"
echo "  uci set remotbot.main.enabled='1'"
echo "  uci commit remotbot"
echo "  /etc/init.d/remotbot start"
exit 0
POSTINST_EOF
        elif [ "$PKG_NAME" = "luci-app-remotbot" ]; then
            cat >> "$CTRL_DIR/postinst" <<'POSTINST_EOF'
# Run uci-defaults
if [ -f /etc/uci-defaults/luci-app-remotbot ]; then
    sh /etc/uci-defaults/luci-app-remotbot && rm -f /etc/uci-defaults/luci-app-remotbot
fi
# Clear LuCI cache
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache/ 2>/dev/null || true
echo "✓ LuCI app installed. Go to Services > Remot Bot"
exit 0
POSTINST_EOF
        fi
    fi
    chmod +x "$CTRL_DIR/postinst"

    # Write prerm
    cat > "$CTRL_DIR/prerm" <<'PRERM_EOF'
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] && exit 0
PRERM_EOF
    if [ "$PKG_NAME" = "remotbot" ]; then
        cat >> "$CTRL_DIR/prerm" <<'PRERM_EOF'
/etc/init.d/remotbot stop 2>/dev/null || true
/etc/init.d/remotbot disable 2>/dev/null || true
exit 0
PRERM_EOF
    elif [ "$PKG_NAME" = "luci-app-remotbot" ]; then
        cat >> "$CTRL_DIR/prerm" <<'PRERM_EOF'
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache/ 2>/dev/null || true
exit 0
PRERM_EOF
    fi
    chmod +x "$CTRL_DIR/prerm"

    # Pack data.tar.gz
    echo "  Packing data..."
    tar -czf "$WORK/data.tar.gz" -C "$DATA_DIR" .

    # Pack control.tar.gz
    echo "  Packing control..."
    tar -czf "$WORK/control.tar.gz" -C "$CTRL_DIR" .

    # Write debian-binary — exactly "2.0\n" (4 bytes)
    printf '2.0\n' > "$WORK/debian-binary"

    # -------------------------------------------------------
    # Create .ipk = gzipped tar (NOT ar/deb format!)
    # IPK format: tar.gz containing:
    #   ./debian-binary
    #   ./control.tar.gz
    #   ./data.tar.gz
    # opkg rejects ar/deb format with "Malformed package file"
    # -------------------------------------------------------
    local IPK_NAME="${PKG_NAME}_${VERSION}-${RELEASE}_${ARCH}.ipk"
    echo "  Creating $IPK_NAME..."
    (
        cd "$WORK"
        tar -czf "$OUTPUT_DIR/$IPK_NAME" \
            ./debian-binary \
            ./control.tar.gz \
            ./data.tar.gz
    )

    echo "  ✓ $OUTPUT_DIR/$IPK_NAME"
}

# -------------------------------------------------------
# Build packages
# -------------------------------------------------------
build_ipk \
    "remotbot" \
    "RemotWRT Telegram Monitoring Bot for OpenWrt / Raspberry Pi 4" \
    "python3, python3-pip"

build_ipk \
    "luci-app-remotbot" \
    "LuCI interface for RemotWRT Telegram Bot (Services > Remot Bot)" \
    "remotbot, luci-base"

# -------------------------------------------------------
# Create Packages index (for opkg repo)
# -------------------------------------------------------
echo ""
echo "→ Generating Packages index..."
PACKAGES_FILE="$OUTPUT_DIR/Packages"
> "$PACKAGES_FILE"

for ipk in "$OUTPUT_DIR"/*.ipk; do
    [ -f "$ipk" ] || continue
    BASENAME=$(basename "$ipk")
    SIZE=$(wc -c < "$ipk")
    MD5=$(md5sum "$ipk" | cut -d' ' -f1)
    SHA256=$(sha256sum "$ipk" | cut -d' ' -f1)

    # Extract control from IPK (IPK = gzipped tar, not ar)
    TMPDIR=$(mktemp -d)
    tar -xzf "$ipk" -C "$TMPDIR" 2>/dev/null || true
    tar -xzf "$TMPDIR/control.tar.gz" -C "$TMPDIR" 2>/dev/null || true
    if [ -f "$TMPDIR/control" ]; then
        cat "$TMPDIR/control" >> "$PACKAGES_FILE"
        echo "Filename: $BASENAME" >> "$PACKAGES_FILE"
        echo "Size: $SIZE" >> "$PACKAGES_FILE"
        echo "MD5Sum: $MD5" >> "$PACKAGES_FILE"
        echo "SHA256sum: $SHA256" >> "$PACKAGES_FILE"
        echo "" >> "$PACKAGES_FILE"
    fi
    rm -rf "$TMPDIR"
done

gzip -9 -k "$PACKAGES_FILE" 2>/dev/null || true

# -------------------------------------------------------
# Summary
# -------------------------------------------------------
echo ""
echo "========================================"
echo " Build Complete!"
echo "========================================"
echo ""
echo "Output files:"
ls -lh "$OUTPUT_DIR"/*.ipk 2>/dev/null
echo ""
echo "To install on OpenWrt:"
echo "  scp dist/*.ipk root@192.168.1.1:/tmp/"
echo "  ssh root@192.168.1.1 'opkg install /tmp/remotbot_*.ipk'"
echo "  ssh root@192.168.1.1 'opkg install /tmp/luci-app-remotbot_*.ipk'"
echo ""
