# RemotWRT-Bot — Top-level Makefile
# Untuk build IPK jalankan: bash scripts/build-ipk.sh

PKG_NAME    := remotbot
PKG_VERSION := 1.0.0
PKG_RELEASE := 1
ARCH        := aarch64_cortex-a72

.PHONY: all build clean install help

all: build

build:
	@echo "Building IPK packages v$(PKG_VERSION)-$(PKG_RELEASE)..."
	@bash scripts/build-ipk.sh $(PKG_VERSION)

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf .build/ dist/
	@echo "Done."

install:
	@echo "Copy IPK ke router OpenWrt..."
	@echo "Usage: make install ROUTER=192.168.1.1"
	@[ -n "$(ROUTER)" ] || (echo "ERROR: set ROUTER=<ip>"; exit 1)
	scp dist/$(PKG_NAME)_$(PKG_VERSION)-$(PKG_RELEASE)_$(ARCH).ipk root@$(ROUTER):/tmp/
	scp dist/luci-app-$(PKG_NAME)_$(PKG_VERSION)-$(PKG_RELEASE)_$(ARCH).ipk root@$(ROUTER):/tmp/
	ssh root@$(ROUTER) "opkg remove $(PKG_NAME) luci-app-$(PKG_NAME) 2>/dev/null; \
	    opkg install /tmp/$(PKG_NAME)_*.ipk --nodeps && \
	    opkg install /tmp/luci-app-$(PKG_NAME)_*.ipk && \
	    rm -rf /tmp/luci-indexcache /tmp/luci-modulecache/"
	@echo "Install selesai!"

help:
	@echo ""
	@echo "RemotWRT-Bot Build System"
	@echo "========================="
	@echo ""
	@echo "  make build              — Build IPK packages"
	@echo "  make clean              — Hapus hasil build"
	@echo "  make install ROUTER=IP  — Build & install ke router"
	@echo ""
	@echo "Atau langsung:"
	@echo "  bash scripts/build-ipk.sh [version]"
	@echo ""
