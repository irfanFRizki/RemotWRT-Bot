#!/bin/bash
# build-ipk.sh — Build IPK OpenWrt (gzip tar format)
# Usage: bash scripts/build-ipk.sh [version]

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
    local WORK="$BUILD_DIR/$PKG_NAME"
    local DATA_DIR="$WORK/data"
    local CTRL_DIR="$WORK/control"

    echo ""
    echo "-> Building $PKG_NAME..."
    mkdir -p "$DATA_DIR" "$CTRL_DIR"

    if [ -d "$FILES_DIR" ]; then
        cp -r "$FILES_DIR/." "$DATA_DIR/"
    fi

    find "$DATA_DIR" -type d -exec chmod 0755 {} \;
    find "$DATA_DIR" -type f -exec chmod 0644 {} \;
    find "$DATA_DIR" -type f -name "*.py" -exec chmod 0755 {} \;

    if [ -d "$DATA_DIR/etc/init.d" ]; then
        find "$DATA_DIR/etc/init.d" -type f -exec chmod 0755 {} \;
    fi
    if [ -d "$DATA_DIR/etc/uci-defaults" ]; then
        find "$DATA_DIR/etc/uci-defaults" -type f -exec chmod 0755 {} \;
    fi

    local INSTALLED_SIZE
    INSTALLED_SIZE=$(du -sk "$DATA_DIR" 2>/dev/null | cut -f1 || echo "100")

    cat > "$CTRL_DIR/control" <<CTRLEOF
Package: $PKG_NAME
Version: $VERSION-$RELEASE
Architecture: $ARCH
Maintainer: RemotWRT <https://github.com/irfanFRizki/RemotWRT-Bot>
Depends: $DEPENDS
Section: net
Priority: optional
Installed-Size: $INSTALLED_SIZE
Description: $PKG_DESC
CTRLEOF

    # conffiles
    if [ -d "$DATA_DIR/etc/config" ]; then
        for f in "$DATA_DIR/etc/config/"*; do
            [ -f "$f" ] && printf "/etc/config/%s\n" "$(basename "$f")"
        done > "$CTRL_DIR/conffiles"
    fi

    # ── postinst ──────────────────────────────────────────
    if [ "$PKG_NAME" = "remotbot" ]; then
        cat > "$CTRL_DIR/postinst" <<'POSTEOF'
#!/bin/sh
[ "${IPKG_NO_SCRIPT}" = "1" ] && exit 0
[ -s ${IPKG_INSTROOT}/lib/functions.sh ] || exit 0
. ${IPKG_INSTROOT}/lib/functions.sh
default_postinst $0 $@

# Buat UCI config jika belum ada
if [ -f /etc/config/remotbot ]; then
    uci -q get remotbot.main >/dev/null 2>&1 || uci set remotbot.main=remotbot
    uci -q get remotbot.main.bot_token >/dev/null 2>&1 || uci set remotbot.main.bot_token=''
    uci -q get remotbot.main.allowed_users >/dev/null 2>&1 || uci set remotbot.main.allowed_users=''
    uci -q get remotbot.main.cgi_online_path >/dev/null 2>&1 || uci set remotbot.main.cgi_online_path='/www/cgi-bin/online'
    uci -q get remotbot.main.enabled >/dev/null 2>&1 || uci set remotbot.main.enabled='0'
    uci -q get remotbot.main.log_level >/dev/null 2>&1 || uci set remotbot.main.log_level='INFO'
    uci commit remotbot 2>/dev/null || true
fi

echo ""
echo "==========================="
echo " RemotWRT Bot Installed!"
echo "==========================="
echo "Next:"
echo "  opkg install luci-app-remotbot_*.ipk"
echo "  LuCI -> Services -> Remot Bot -> Settings"
echo ""
exit 0
POSTEOF

    elif [ "$PKG_NAME" = "luci-app-remotbot" ]; then
        cat > "$CTRL_DIR/postinst" <<'POSTEOF'
#!/bin/sh
[ "${IPKG_NO_SCRIPT}" = "1" ] && exit 0
[ -s ${IPKG_INSTROOT}/lib/functions.sh ] || exit 0
. ${IPKG_INSTROOT}/lib/functions.sh
default_postinst $0 $@

if [ -f /etc/uci-defaults/luci-app-remotbot ]; then
    sh /etc/uci-defaults/luci-app-remotbot && rm -f /etc/uci-defaults/luci-app-remotbot
fi
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache/ 2>/dev/null || true
echo "==========================="
echo " LuCI Remot Bot Installed!"
echo " Go: Services > Remot Bot"
echo "==========================="
exit 0
POSTEOF

    else
        printf '#!/bin/sh\n[ -n "${IPKG_INSTROOT}" ] && exit 0\nexit 0\n' > "$CTRL_DIR/postinst"
    fi
    chmod 0755 "$CTRL_DIR/postinst"

    # ── prerm ─────────────────────────────────────────────
    if [ "$PKG_NAME" = "remotbot" ]; then
        cat > "$CTRL_DIR/prerm" <<'PRMEOF'
#!/bin/sh
[ "${IPKG_NO_SCRIPT}" = "1" ] && exit 0
[ -s ${IPKG_INSTROOT}/lib/functions.sh ] || exit 0
. ${IPKG_INSTROOT}/lib/functions.sh
default_prerm $0 $@
/etc/init.d/remotbot stop    2>/dev/null || true
/etc/init.d/remotbot disable 2>/dev/null || true
exit 0
PRMEOF
    elif [ "$PKG_NAME" = "luci-app-remotbot" ]; then
        cat > "$CTRL_DIR/prerm" <<'PRMEOF'
#!/bin/sh
[ "${IPKG_NO_SCRIPT}" = "1" ] && exit 0
[ -s ${IPKG_INSTROOT}/lib/functions.sh ] || exit 0
. ${IPKG_INSTROOT}/lib/functions.sh
default_prerm $0 $@
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache/ 2>/dev/null || true
exit 0
PRMEOF
    else
        printf '#!/bin/sh\nexit 0\n' > "$CTRL_DIR/prerm"
    fi
    chmod 0755 "$CTRL_DIR/prerm"

    # ── Pack ──────────────────────────────────────────────
    echo "  Packing data..."
    tar -czf "$WORK/data.tar.gz" \
        --numeric-owner --owner=0 --group=0 \
        -C "$DATA_DIR" .

    echo "  Packing control..."
    tar -czf "$WORK/control.tar.gz" \
        --numeric-owner --owner=0 --group=0 \
        -C "$CTRL_DIR" .

    printf '2.0\n' > "$WORK/debian-binary"

    # IPK = gzip tar, nama TANPA ./, data SEBELUM control
    local IPK_NAME="${PKG_NAME}_${VERSION}-${RELEASE}_${ARCH}.ipk"
    echo "  Creating $IPK_NAME..."
    ( cd "$WORK" && tar -czf "$OUTPUT_DIR/$IPK_NAME" \
        --numeric-owner --owner=0 --group=0 \
        debian-binary data.tar.gz control.tar.gz )

    echo "  OK -> dist/$IPK_NAME"
}

# ── Build ─────────────────────────────────────────────────
# Depends minimal: hanya python3-light + pip
# python3-multiprocessing TIDAK dimasukkan (sering timeout download)
# python-telegram-bot & requests diinstall oleh init.d saat start pertama
build_ipk "remotbot" \
    "RemotWRT Telegram Monitoring Bot for OpenWrt / Raspberry Pi 4" \
    "python3-light, python3-logging, python3-asyncio, python3-urllib, python3-codecs, python3-pip"

build_ipk "luci-app-remotbot" \
    "LuCI interface for RemotWRT Telegram Bot (Services > Remot Bot)" \
    "remotbot, luci-base"

# ── Packages index ────────────────────────────────────────
echo ""
echo "-> Generating Packages index..."
PKGS="$OUTPUT_DIR/Packages"
> "$PKGS"
for ipk in "$OUTPUT_DIR"/*.ipk; do
    [ -f "$ipk" ] || continue
    BASENAME=$(basename "$ipk")
    SIZE=$(wc -c < "$ipk")
    MD5=$(md5sum "$ipk" | cut -d' ' -f1)
    SHA256=$(sha256sum "$ipk" | cut -d' ' -f1)
    TMP=$(mktemp -d)
    tar -xzf "$ipk" -C "$TMP" 2>/dev/null || true
    tar -xzf "$TMP/control.tar.gz" -C "$TMP" 2>/dev/null || true
    if [ -f "$TMP/control" ]; then
        cat "$TMP/control"         >> "$PKGS"
        echo "Filename: $BASENAME" >> "$PKGS"
        echo "Size: $SIZE"         >> "$PKGS"
        echo "MD5Sum: $MD5"        >> "$PKGS"
        echo "SHA256sum: $SHA256"  >> "$PKGS"
        echo ""                    >> "$PKGS"
    fi
    rm -rf "$TMP"
done
gzip -9 -k "$PKGS" 2>/dev/null || true

echo ""
echo "========================================"
echo " Build Complete!"
echo "========================================"
ls -lh "$OUTPUT_DIR"/*.ipk 2>/dev/null
echo ""
echo "Install ke OpenWrt:"
echo "  scp dist/*.ipk root@192.168.7.1:/tmp/"
echo "  opkg install /tmp/remotbot_*.ipk --nodeps"
echo "  opkg install /tmp/luci-app-remotbot_*.ipk"
echo ""
