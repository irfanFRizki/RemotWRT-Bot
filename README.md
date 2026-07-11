# 🤖 RemotWRT Bot

Telegram Monitoring Bot untuk OpenWrt di Raspberry Pi 4 — dikemas sebagai IPK Package dengan antarmuka LuCI.

[![Build IPK](https://github.com/irfanFRizki/RemotWRT-Bot/actions/workflows/build-ipk.yml/badge.svg)](https://github.com/irfanFRizki/RemotWRT-Bot/actions/workflows/build-ipk.yml)

---

## ✨ Fitur

| Fitur | Deskripsi |
|---|---|
| 🖥 CPU & RAM | Suhu, usage, load average, uptime, memori |
| 👥 Online Users | Daftar perangkat terhubung via DHCP + ARP |
| 📊 Traffic | Statistik live + harian + bulanan (vnstat) |
| 🌍 My IP | Info IP publik + ISP + lokasi |
| 🔍 Ping | Test koneksi ke host |
| ⚡ Speedtest | Ookla / speedtest-cli otomatis |
| 💿 Disk | Info penggunaan storage |
| 🔒 Leak Test | DNS & IP leak check |
| 🛡 AdBlock | Cek status adblock |
| ⚙️ Services | Monitor & kontrol service OpenWrt |
| 🐳 Docker | Info container yang berjalan |
| 💻 Command | Eksekusi shell command remote |
| 🌡 Alert CPU | Notifikasi otomatis CPU terlalu panas |
| 💾 Alert RAM | Notifikasi otomatis RAM hampir penuh |
| 📡 Alert WAN | Notifikasi WAN putus + durasi down |
| ⚠️ Alert Device | Deteksi perangkat tak dikenal di jaringan |
| 🚫 Blokir MAC | Blokir/izinkan device via Telegram |
| 🌐 Multi-bahasa | Toggle Indonesia / English |
| ⚙️ Settings | Konfigurasi notifikasi dari Telegram |

---

## 📁 Struktur Project

```
RemotWRT-Bot/
├── .github/workflows/build-ipk.yml   ← Auto-build IPK via GitHub Actions
├── Makefile                           ← Build helper
├── README.md
├── scripts/
│   └── build-ipk.sh                  ← Build IPK tanpa OpenWrt SDK
└── packages/
    ├── remotbot/                      ← Package bot utama
    │   └── files/
    │       ├── usr/bin/pi4Bot.py      ← Bot script (baca config dari UCI)
    │       ├── www/cgi-bin/online     ← CGI daftar device online
    │       ├── etc/init.d/remotbot    ← Service script (procd)
    │       └── etc/config/remotbot   ← UCI config template
    └── luci-app-remotbot/             ← Package LuCI interface
        └── files/
            ├── usr/lib/lua/luci/
            │   ├── controller/remotbot.lua
            │   ├── model/cbi/remotbot/dashboard.lua
            │   ├── model/cbi/remotbot/settings.lua
            │   └── view/remotbot/dashboard_status.htm
            ├── usr/share/rpcd/acl.d/luci-app-remotbot.json
            └── etc/uci-defaults/luci-app-remotbot
```

---

## 🚀 Instalasi

### Download dari GitHub Releases / Actions

```sh
# Di perangkat OpenWrt
cd /tmp

# Download IPK dari Releases atau Actions Artifacts
wget <URL_remotbot_1.0.0-1_aarch64_cortex-a72.ipk>
wget <URL_luci-app-remotbot_1.0.0-1_aarch64_cortex-a72.ipk>

# Uninstall lama jika ada
opkg remove remotbot luci-app-remotbot 2>/dev/null

# Install — gunakan --nodeps untuk remotbot
opkg install remotbot_*.ipk --nodeps
opkg install luci-app-remotbot_*.ipk

# Bersihkan LuCI cache
rm -rf /tmp/luci-indexcache /tmp/luci-modulecache/
```

### Build Manual

```sh
git clone https://github.com/irfanFRizki/RemotWRT-Bot
cd RemotWRT-Bot
bash scripts/build-ipk.sh 1.0.0
# Output: dist/*.ipk
```

---

## ⚙️ Konfigurasi

### Via LuCI (Recommended)

1. Buka LuCI → **Services → Remot Bot → Settings**
2. Isi **Telegram Bot Token** (buat via [@BotFather](https://t.me/BotFather))
3. Isi **Allowed User IDs** (cari via [@userinfobot](https://t.me/userinfobot))
4. Atur notifikasi otomatis (suhu CPU, RAM, WAN, device asing)
5. Pilih bahasa (Indonesia/English)
6. Centang **Enable** → **Save & Apply**
7. Buka **Dashboard → Start**

### Via UCI (Terminal)

```sh
# Konfigurasi dasar
uci set remotbot.main.bot_token='1234567890:AAECVsHHxxxx'
uci set remotbot.main.allowed_users='5645537022'
uci set remotbot.main.enabled='1'

# Opsional: notifikasi
uci set remotbot.main.cpu_temp_threshold='75'
uci set remotbot.main.ram_threshold='85'
uci set remotbot.main.wan_timeout_minutes='60'
uci set remotbot.main.language='id'

# Opsional: MAC whitelist untuk deteksi device asing
uci add_list remotbot.main.mac_whitelist='aa:bb:cc:dd:ee:ff'

uci commit remotbot
/etc/init.d/remotbot start
```

---

## 🔔 Notifikasi Otomatis

Bot secara otomatis mengirim alert ke Telegram jika:

| Kondisi | Default | Setting |
|---|---|---|
| Suhu CPU > threshold | 75°C | `cpu_temp_threshold` |
| RAM > threshold | 85% | `ram_threshold` |
| WAN terputus | Langsung | `notify_wan` |
| WAN putus terlalu lama | 60 menit | `wan_timeout_minutes` |
| Device tidak ada di whitelist | Aktif jika whitelist diisi | `notify_unknown_device` |

---

## 🛠 Service Management

```sh
/etc/init.d/remotbot start    # Start bot
/etc/init.d/remotbot stop     # Stop bot
/etc/init.d/remotbot restart  # Restart bot
/etc/init.d/remotbot status   # Cek status
/etc/init.d/remotbot enable   # Enable auto-start
/etc/init.d/remotbot disable  # Disable auto-start
```

---

## 🔄 Auto Build (GitHub Actions)

IPK akan otomatis di-build setiap ada push ke branch `main`/`master`.

```sh
# Cara release baru
git tag v1.0.1 && git push origin v1.0.1
```

---

## 📋 Dependencies

| Package | Keterangan |
|---|---|
| `python3-light` | Python runtime minimal |
| `python3-pip` | Package manager Python |
| `python-telegram-bot` | Auto-install via pip saat start |
| `requests` | Auto-install via pip saat start |

> **Catatan:** Gunakan `--nodeps` saat install remotbot untuk menghindari
> `python3-multiprocessing` yang sering timeout saat download.
> Python3 sudah tersedia di OpenWrt 24.10.

---

## 📄 License

MIT License — © 2024 [irfanFRizki](https://github.com/irfanFRizki)
