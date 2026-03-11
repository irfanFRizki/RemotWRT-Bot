# RemotWRT Bot 🤖

OpenWRT Telegram Monitoring Bot untuk Raspberry Pi 4, dikemas sebagai paket `.ipk` dengan antarmuka LuCI.

[![Build IPK](https://github.com/irfanFRizki/RemotWRT-Bot/actions/workflows/build.yml/badge.svg)](https://github.com/irfanFRizki/RemotWRT-Bot/actions/workflows/build.yml)

---

## 📱 Fitur Bot Telegram

### Menu Utama
| Menu | Fungsi |
|------|--------|
| 🖥 CPU & RAM | Monitor suhu, load, memory |
| 👥 Online Users | Daftar device terhubung di jaringan |
| 📊 Traffic | Statistik bandwidth via vnstat |
| 🌍 My IP | Info IP publik + ISP + lokasi |
| 🔍 Ping | Test koneksi ke 8.8.8.8 |
| ⚡ Speedtest | Test kecepatan internet (Ookla/speedtest-cli) |
| 💿 Disk | Info disk usage |
| 🔒 Leak Test | DNS/IP leak test + deteksi VPN |
| 🛡 AdBlock | Test apakah AdBlock aktif |
| ⚙️ Services | Status openclash / nikki / cloudflared |
| 🐳 Containers | Info Docker / Podman |
| 💻 Command | Jalankan perintah shell kustom |
| 🚫 Blokir Device | Manajemen blokir MAC address |
| ⚙️ Settings | Pengaturan bahasa & notifikasi |

### 🔔 Notifikasi Otomatis
Bot memantau sistem setiap 1 menit dan mengirim alert otomatis:

| Alert | Kondisi Default | Cooldown |
|-------|----------------|---------|
| 🌡 CPU Panas | Suhu > 75°C | 30 menit |
| 💾 RAM Penuh | Penggunaan > 85% | 30 menit |
| 📡 WAN Putus | Koneksi internet terputus | Langsung |
| ⏱ WAN Lama Putus | Masih putus > 60 menit | Sekali |
| ✅ WAN Pulih | Koneksi kembali + durasi downtime | Langsung |
| ⚠️ Device Tak Dikenal | MAC tidak ada di whitelist | Per MAC |

> Semua threshold bisa diubah di `/etc/remotbot/config.json`

### 🚫 Blokir Device Tidak Terdaftar
- Isi whitelist MAC di `config.json` atau lewat Settings
- Jika device baru masuk jaringan → bot kirim alert + tombol **Blokir / Izinkan**
- Blokir menggunakan `iptables` + disimpan ke `uci firewall` (tetap aktif setelah reboot)

### 🌐 Multi-bahasa
- Bahasa Indonesia 🇮🇩 dan English 🇬🇧
- Toggle langsung dari menu ⚙️ Settings di Telegram

---

## 📦 Instalasi

### Cara 1 — Download dari GitHub Releases (Termux/PC)

```bash
# Download IPK terbaru
wget https://github.com/irfanFRizki/RemotWRT-Bot/releases/latest/download/luci-app-remotbot_1.0.0-1_all.ipk

# Upload ke router
scp luci-app-remotbot_*.ipk root@192.168.1.1:/tmp/

# Install via SSH
ssh root@192.168.1.1 "opkg install /tmp/luci-app-remotbot_*.ipk"
```

### Cara 2 — Clone & Build (Termux)

```bash
pkg install git
git clone https://github.com/irfanFRizki/RemotWRT-Bot.git
cd RemotWRT-Bot
bash scripts/build-ipk.sh
scp dist/luci-app-remotbot_*.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1 "opkg install /tmp/luci-app-remotbot_*.ipk"
```

---

## ⚙️ Konfigurasi

Setelah install, buka LuCI: **Services → Remot Bot → Settings**

Isi:
- **Bot Token** — Dari [@BotFather](https://t.me/BotFather)
- **Allowed User IDs** — ID kamu dari [@userinfobot](https://t.me/userinfobot)

Lalu buka **Dashboard** → klik **▶ Start**.

### Konfigurasi Lanjutan (`/etc/remotbot/config.json`)

```json
{
    "bot_token": "TOKEN_DARI_BOTFATHER",
    "allowed_users": [123456789],
    "cgi_online_path": "/www/cgi-bin/online",
    "language": "id",

    "cpu_temp_threshold": 75,
    "ram_threshold": 85,
    "wan_timeout_minutes": 60,

    "mac_whitelist": [
        "aa:bb:cc:dd:ee:ff",
        "11:22:33:44:55:66"
    ],

    "notify_cpu_temp": true,
    "notify_ram": true,
    "notify_wan": true,
    "notify_unknown_device": true
}
```

> **mac_whitelist** — Daftar MAC yang diizinkan di jaringan. Jika kosong, fitur blokir device tak dikenal tidak aktif.

---

## 📂 Struktur Project

```
RemotWRT-Bot/
├── src/
│   ├── pi4Bot.py                         # Main bot script
│   └── cgi-bin/
│       └── online                        # CGI script daftar device online
├── luci-app-remotbot/
│   ├── root/
│   │   ├── etc/init.d/remotbot           # Service script (procd, autostart)
│   │   ├── etc/config/remotbot           # Default config OpenWrt UCI
│   │   └── usr/bin/remotbot-install-deps # Auto installer Python deps
│   ├── luasrc/
│   │   ├── controller/remotbot.lua       # LuCI controller (menu & API)
│   │   └── model/cbi/remotbot/settings.lua # Halaman Settings LuCI
│   └── htdocs/
│       └── luci-static/.../dashboard.htm # Dashboard LuCI
├── scripts/
│   └── build-ipk.sh                      # Build IPK manual
├── .github/
│   └── workflows/build.yml               # GitHub Actions CI/CD
├── Makefile                              # OpenWrt build system
└── README.md
```

---

## 🔄 GitHub Actions (Auto Build IPK)

Setiap `push` ke branch `main` atau `master` akan otomatis:
1. Hitung versi baru dari jumlah commit
2. Build file `.ipk`
3. Generate changelog dari commit messages
4. Upload sebagai GitHub Release

**Contoh format changelog:**
```
## v1.2.3 — 2026-03-11

### Perubahan
- feat: tambah notifikasi WAN putus
- fix: perbaiki parsing suhu CPU
- refactor: update LuCI dashboard

### Info Build
- Commit: `abc1234...`
- Branch: `main`
```

> **Tips:** Tulis commit message yang deskriptif agar changelog informatif.
> ```bash
> git commit -m "feat: tambah alert device tak dikenal"
> git commit -m "fix: perbaiki timeout speedtest"
> ```

---

## 📱 Upload via Termux

```bash
# Setup
pkg install git openssh
git config --global user.name "irfanFRizki"
git config --global user.email "email@kamu.com"

# Clone repo
git clone https://github.com/irfanFRizki/RemotWRT-Bot.git
cd RemotWRT-Bot

# Edit file, lalu push
git add .
git commit -m "feat: deskripsi perubahan"
git push origin main
# GitHub Actions otomatis build IPK baru
```

> Gunakan **Personal Access Token (PAT)** saat diminta password.
> Buat di: GitHub → Settings → Developer settings → Personal access tokens

---

## 📋 Dependencies (Terinstall Otomatis)

| Package | Cara Install |
|---------|-------------|
| `python3` | opkg |
| `python3-pip` | opkg |
| `python3-requests` | opkg |
| `python-telegram-bot` | pip3 |

Atau install manual:
```bash
sh /usr/bin/remotbot-install-deps
```

---

## 🛠 Troubleshooting

**Bot tidak start:**
```bash
# Cek log
logread | grep remotbot
cat /tmp/remotbot-install.log

# Cek config
cat /etc/remotbot/config.json

# Start manual
python3 /usr/share/remotbot/pi4Bot.py
```

**Dependency error:**
```bash
sh /usr/bin/remotbot-install-deps
```

**CGI online tidak berjalan:**
```bash
chmod +x /www/cgi-bin/online
bash /www/cgi-bin/online
```
