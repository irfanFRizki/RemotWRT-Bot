include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-remotbot
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-remotbot
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=LuCI Support for RemotWRT Bot
  DEPENDS:=+luci-base +python3 +python3-pip
  PKGARCH:=all
endef

define Build/Compile
endef

define Package/luci-app-remotbot/install
	$(INSTALL_DIR) $(1)/usr/share/remotbot
	$(INSTALL_BIN) ./src/pi4Bot.py $(1)/usr/share/remotbot/pi4Bot.py
	$(INSTALL_DIR) $(1)/www/cgi-bin
	$(INSTALL_BIN) ./src/cgi-bin/online $(1)/www/cgi-bin/online
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./luci-app-remotbot/root/etc/init.d/remotbot $(1)/etc/init.d/remotbot
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_DATA) ./luci-app-remotbot/root/etc/config/remotbot $(1)/etc/config/remotbot
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) ./luci-app-remotbot/root/usr/bin/remotbot-install-deps $(1)/usr/bin/remotbot-install-deps
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/controller
	$(INSTALL_DATA) ./luci-app-remotbot/luasrc/controller/remotbot.lua $(1)/usr/lib/lua/luci/controller/remotbot.lua
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/model/cbi/remotbot
	$(INSTALL_DATA) ./luci-app-remotbot/luasrc/model/cbi/remotbot/settings.lua $(1)/usr/lib/lua/luci/model/cbi/remotbot/settings.lua
	$(INSTALL_DIR) $(1)/www/luci-static/resources/view/remotbot
	$(INSTALL_DATA) ./luci-app-remotbot/htdocs/luci-static/resources/view/remotbot/dashboard.htm $(1)/www/luci-static/resources/view/remotbot/dashboard.htm
endef

$(eval $(call BuildPackage,luci-app-remotbot))
