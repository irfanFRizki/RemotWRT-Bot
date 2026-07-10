# Package: remotbot
# Untuk build gunakan: bash ../../scripts/build-ipk.sh

PKG_NAME    := remotbot
PKG_VERSION := 1.0.5
PKG_RELEASE := 2

PKG_LICENSE := MIT
PKG_MAINTAINER := RemotWRT-Bot Team

include $(TOPDIR)/rules.mk

define Package/remotbot
  SECTION:=net
  CATEGORY:=Network
  TITLE:=RemotWRT-Bot - Telegram Bot untuk OpenWrt Monitoring
  DEPENDS:=+python3 +python3-light +libuci +curl +iptables +opennds +voucher-wifi
endef

define Package/remotbot/description
  Telegram bot untuk monitoring dan management OpenWrt dengan fitur:
  - Device monitoring via MAC whitelist
  - OpenNDS captive portal integration
  - FAS (Forwarding Authentication Service) server
  - LuCI web interface untuk pending approval
endef

define Build/Compile
endef

define Package/remotbot/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/files/usr/bin/pi4Bot.py $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/files/usr/bin/fas_server.py $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/files/usr/bin/remotbot_actions.py $(1)/usr/bin/
	
	$(INSTALL_DIR) $(1)/usr/share/remotbot
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/files/usr/share/remotbot/requirements.txt $(1)/usr/share/remotbot/
	
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/files/etc/init.d/remotbot $(1)/etc/init.d/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/files/etc/init.d/remotbot-fas $(1)/etc/init.d/
	
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) $(PKG_BUILD_DIR)/files/etc/config/remotbot $(1)/etc/config/
	
	# Install LuCI files
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/controller
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/luasrc/controller/remotbot.lua $(1)/usr/lib/lua/luci/controller/
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/controller/api
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/luasrc/controller/api/remotbot_pending.lua $(1)/usr/lib/lua/luci/controller/api/
	
	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/view/remotbot
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/luasrc/view/remotbot/pending_list.htm $(1)/usr/lib/lua/luci/view/remotbot/
endef

define Package/remotbot/postinst
#!/bin/sh
if [ -z "$${IPKG_INSTROOT}" ]; then
	grep -q '^remotbot:' /etc/passwd || echo 'remotbot:x:65530:65530:remotbot:/var/run:/bin/false' >> /etc/passwd
	grep -q '^remotbot:' /etc/group || echo 'remotbot:x:65530:' >> /etc/group
fi
exit 0
endef

$(eval $(call BuildPackage,remotbot))
