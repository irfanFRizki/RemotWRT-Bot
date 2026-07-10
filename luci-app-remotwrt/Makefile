#
# Copyright (C) 2024 RemotWRT Project
#
# This is free software, licensed under the Apache License, Version 2.0 .
#

include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI Support for RemotWRT - Advanced WiFi Management
LUCI_DEPENDS:=+opennds +luci-base +rpcd +uhttpd
LUCI_PKGARCH:=all

PKG_NAME:=luci-app-remotwrt
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
