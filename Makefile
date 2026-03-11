include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-remotbot
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-remotbot
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=LuCI Support for RemotWRT Bot
  DEPENDS:=+luci-base +python3 +python3-pip
  PKGARCH:=all
endef

define Package/luci-app-remotbot/description
  OpenWRT Telegram Monitoring Bot untuk Raspberry Pi 4.
  Menyediakan menu di LuCI Services > Remot Bot dengan
  Dashboard dan Settings untuk konfigurasi Telegram Bot Token
  dan Chat ID. Auto-install python dependencies.
endef

define Build/Compile
endef

define Package/luci-app-remotbot/install
	$(INSTALL_DIR) $(1)/usr/share/remotbot
	$(INSTALL_BIN) ./src/pi4Bot.py $(1)/usr/share/remotbot/pi4Bot.py

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./luci-app-remotbot/root/etc/init.d/remotbot $(1)/etc/init.d/remotbot

	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_DATA) ./luci-app-remotbot/root/etc/config/remotbot $(1)/etc/config/remotbot

	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) ./luci-app-remotbot/root/usr/bin/remotbot-install-deps $(1)/usr/bin/remotbot-install-deps

	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/controller
	$(INSTALL_DATA) ./luci-app-remotbot/luasrc/controller/remotbot.lua \
		$(1)/usr/lib/lua/luci/controller/remotbot.lua

	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/model/cbi/remotbot
	$(INSTALL_DATA) ./luci-app-remotbot/luasrc/model/cbi/remotbot/settings.lua \
		$(1)/usr/lib/lua/luci/model/cbi/remotbot/settings.lua

	$(INSTALL_DIR) $(1)/www/luci-static/resources/view/remotbot
	$(INSTALL_DATA) ./luci-app-remotbot/htdocs/luci-static/resources/view/remotbot/dashboard.htm \
		$(1)/www/luci-static/resources/view/remotbot/dashboard.htm
endef

define Package/luci-app-remotbot/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] && exit 0

# Create config directory
mkdir -p /etc/remotbot

# Create default config if not exists
if [ ! -f /etc/remotbot/config.json ]; then
    cat > /etc/remotbot/config.json <<'JSONEOF'
{
    "bot_token": "",
    "allowed_users": [],
    "cgi_online_path": "/www/cgi-bin/online"
}
JSONEOF
fi

# Make scripts executable
chmod +x /etc/init.d/remotbot
chmod +x /usr/bin/remotbot-install-deps
chmod +x /usr/share/remotbot/pi4Bot.py

# Enable service
/etc/init.d/remotbot enable

# Install python dependencies in background
echo "Installing Python dependencies (this may take a few minutes)..."
sh /usr/bin/remotbot-install-deps > /tmp/remotbot-install.log 2>&1 &

# Clear LuCI cache
rm -rf /tmp/luci-*

echo ""
echo "=== RemotWRT Bot Installed ==="
echo "Configure via LuCI: Services > Remot Bot > Settings"
echo "Set your Bot Token and Telegram User ID, then Start the bot."
echo ""
exit 0
endef

define Package/luci-app-remotbot/prerm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] && exit 0
/etc/init.d/remotbot stop 2>/dev/null
/etc/init.d/remotbot disable 2>/dev/null
exit 0
endef

$(eval $(call BuildPackage,luci-app-remotbot))
