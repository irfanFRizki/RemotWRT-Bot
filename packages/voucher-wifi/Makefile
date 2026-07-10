# Makefile untuk Paket Voucher WiFi RemotWRT
# Build dengan: make package/voucher-wifi/compile V=s

include $(TOPDIR)/rules.mk

PKG_NAME := voucher-wifi
PKG_VERSION := 1.0.5
PKG_RELEASE := 1
PKG_ARCH := all

PKG_LICENSE:=MIT
PKG_MAINTAINER:=RemotWRT Team <support@remotwrt.com>

include $(INCLUDE_DIR)/package.mk

define Package/voucher-wifi
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=Applications
  TITLE:=Sistem Login WiFi Voucher dengan OpenNDS
  URL:=https://github.com/remotwrt/remotwrt-bot
  DEPENDS:=+opennds +uhttpd +lua +libuci-lua +iptables
  PKGARCH:=all
endef

define Package/voucher-wifi/description
  Sistem login WiFi voucher untuk OpenWRT dengan fitur:
  - Halaman login custom dengan kategori (Keluarga/Pengguna Lain)
  - Manajemen voucher via web interface LuCI
  - Integrasi firewall whitelist untuk akses otomatis
  - Dashboard monitoring client terautentikasi
  - Pesan khusus "WiFi Pribadi tidak dipakai secara umum"
endef

define Build/Compile
	# Tidak perlu compile karena semua file script dan konfigurasi
endef

define Package/voucher-wifi/install
	$(INSTALL_DIR) $(1)/etc/opennds/theme
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_DIR) $(1)/etc/config
	
	# Install tema OpenNDS
	$(INSTALL_DATA) ./files/etc/opennds/theme/login.html $(1)/etc/opennds/theme/login.html
	
	# Install script autentikasi
	$(INSTALL_BIN) ./files/usr/bin/voucher_auth.sh $(1)/usr/bin/voucher_auth.sh
	
	# Install helper scripts
	$(INSTALL_BIN) ./files/usr/bin/remotwrt_firewall_helper.sh $(1)/usr/bin/remotwrt_firewall_helper.sh
	$(INSTALL_BIN) ./files/usr/bin/remotwrt_session_cleanup.sh $(1)/usr/bin/remotwrt_session_cleanup.sh
	
	# Install konfigurasi default
	$(INSTALL_CONF) ./files/etc/config/opennds $(1)/etc/config/opennds.default
	
	# Install postinst script
	$(INSTALL_BIN) ./files/postinst $(1)/postinst
endef

$(eval $(call BuildPackage,voucher-wifi))
