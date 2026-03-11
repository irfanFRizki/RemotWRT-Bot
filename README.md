# RemotWRT Bot 🤖

OpenWRT Telegram Monitoring Bot untuk Raspberry Pi 4, dikemas sebagai paket `.ipk` dengan antarmuka LuCI.

[![Build IPK](https://github.com/irfanFRizki/RemotWRT-Bot/actions/workflows/build.yml/badge.svg)](https://github.com/irfanFRizki/RemotWRT-Bot/actions/workflows/build.yml)

---

## 📦 Instalasi

### Cara 1 — Download dari GitHub Releases (Termux/PC)

```bash
# Di Termux / Terminal PC
# Download IPK terbaru dari GitHub Releases
wget https://github.com/irfanFRizki/RemotWRT-Bot/releases/latest/download/luci-app-remotbot_1.0.0-1_all.ipk

# Upload ke OpenWrt via SCP
scp luci-app-remotbot_*.ipk root@192.168.1.1:/tmp/

# Install via SSH
ssh root@192.168.1.1 "opkg install /tmp/luci-app-remotbot_*.ipk"
```

### Cara 2 — Clone & Build Sendiri (Termux)

```bash
# Install git di Termux
pkg install git

# Clone repo
git clone https://github.com/irfanFRizki/RemotWRT-Bot.git
cd RemotWRT-Bot

# Build IPK
bash scripts/build-ipk.sh

# Upload ke router
scp dist/luci-app-remotbot_*.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1 "opkg install /tmp/luci-app-remotbot_*.ipk"
```

---

## ⚙️ Konfigurasi

Setelah install, buka LuCI:

**Services → Remot Bot → Settings**

Isi:
- **Bot Token** — Dapatkan dari [@BotFather](https://t.me/BotFather)
- **Allowed User IDs** — Dapatkan ID kamu dari [@userinfobot](https://t.me/userinfobot)

Lalu buka **Dashboard** dan klik **▶ Start**.

---

## 🔧 Fitur Bot Telegram

| Menu | Fungsi |
|------|--------|
| 🖥 CPU & RAM | Monitor suhu, load, memory |
| 👥 Online Users | Daftar device terhubung |
| 📊 Traffic | Statistik bandwidth (vnstat) |
| 🌍 My IP | Info IP publik |
| 🔍 Ping | Test koneksi |
| ⚡ Speedtest | Test kecepatan internet |
| 💿 Disk | Info disk usage |
| 🔒 Leak Test | DNS/IP leak test |
| 🛡 AdBlock | Test adblock |
| ⚙️ Services | Status openclash/nikki/cloudflared |
| 🐳 Containers | Info Docker/Podman |
| 💻 Command | Jalankan command kustom |

---

## 📂 Struktur Project

```
RemotWRT-Bot/
├── src/
│   └── pi4Bot.py                    # Main bot script
├── luci-app-remotbot/
│   ├── root/
│   │   ├── etc/init.d/remotbot      # Service script (procd)
│   │   ├── etc/config/remotbot      # Default config
│   │   └── usr/bin/remotbot-install-deps  # Auto installer deps
│   ├── luasrc/
│   │   ├── controller/remotbot.lua  # LuCI controller
│   │   └── model/cbi/remotbot/settings.lua
│   └── htdocs/
│       └── luci-static/.../dashboard.htm
├── scripts/
│   └── build-ipk.sh                 # Build script manual
├── .github/
│   └── workflows/build.yml          # GitHub Actions CI/CD
├── Makefile                         # OpenWrt build system
└── README.md
```

---

## 🔄 GitHub Actions (Auto Build)

Setiap push ke `main/master` akan otomatis:
1. Build file `.ipk`
2. Upload sebagai GitHub Release

---

## 📱 Upload via Termux ke GitHub

```bash
# Setup git di Termux
pkg install git openssh

# Clone & setup
git clone https://github.com/irfanFRizki/RemotWRT-Bot.git
cd RemotWRT-Bot
git config user.email "email@kamu.com"
git config user.name "Nama Kamu"

# Edit file, lalu push
git add .
git commit -m "Update bot script"
git push origin main
# GitHub Actions akan otomatis build IPK baru
```

---

## 📋 Dependencies yang Diinstall Otomatis

- `python3`
- `python3-pip`
- `python3-requests`
- `python-telegram-bot` (via pip)

Atau install manual:
```bash
sh /usr/bin/remotbot-install-deps
```
