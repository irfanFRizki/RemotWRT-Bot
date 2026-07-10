# 🤖 RemotWRT Bot

Telegram Monitoring Bot untuk OpenWrt di Raspberry Pi 4 — dikemas sebagai IPK Package dengan antarmuka LuCI, terintegrasi dengan **OpenNDS Captive Portal** untuk sistem login voucher WiFi.

[![Build IPK](https://github.com/irfanFRizki/RemotWRT-Bot/actions/workflows/build-ipk.yml/badge.svg)](https://github.com/irfanFRizki/RemotWRT-Bot/actions/workflows/build-ipk.yml)

---

## ✨ Fitur Utama

### 🤖 Monitoring & Kontrol Telegram
| Fitur | Deskripsi |
|---|---|
| 🖥 CPU & RAM | Suhu, usage, load average, uptime, memori |
| 👥 Online Users | Daftar perangkat terhubung via DHCP + ARP + **OpenNDS** |
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

### 🎫 Sistem Login Voucher WiFi (OpenNDS)
| Fitur | Deskripsi |
|---|---|
| 🏠 Kategori Keluarga | Login dengan voucher khusus untuk anggota keluarga |
| 👤 Kategori Pengguna Lain | Login dengan pesan "WiFi Pribadi tidak dipakai secara umum" |
| 🔑 Validasi Voucher | Script autentikasi custom untuk validasi kode voucher |
| 🛡 Firewall Integration | IP yang sudah disetujui di firewall langsung akses tanpa login |
| 📱 Dashboard LuCI | Manajemen voucher dan monitoring client terintegrasi |
| 🎨 Tema Custom | Halaman login modern dengan dropdown kategori |

---

## 📁 Struktur Project

```
RemotWRT-Bot/
├── .github/workflows/build-ipk.yml   ← Auto-build IPK via GitHub Actions
├── Makefile                           ← Build helper
├── README.md
├── scripts/
│   └── build-ipk.sh                  ← Build IPK tanpa OpenWrt SDK
├── opennds-voucher-theme/            ← Tema & script OpenNDS
│   ├── install.sh                    ← Installer otomatis
│   ├── theme/
│   │   └── login.html                ← Halaman login custom (Keluarga/Pengguna Lain)
│   └── scripts/
│       └── voucher_auth.sh           ← Script validasi voucher
└── packages/
    ├── remotbot/                      ← Package bot utama
    │   └── files/
    │       ├── usr/bin/pi4Bot.py      ← Bot script (baca config dari UCI)
    │       ├── www/cgi-bin/online     ← CGI daftar device online (CGI+OpenNDS+ARP)
    │       ├── etc/init.d/remotbot    ← Service script (procd)
    │       └── etc/config/remotbot   ← UCI config template
    └── luci-app-remotbot/             ← Package LuCI interface
        └── files/
            ├── usr/lib/lua/luci/
            │   ├── controller/remotbot.lua
            │   ├── model/cbi/remotbot/dashboard.lua
            │   ├── model/cbi/remotbot/settings.lua
            │   ├── model/cbi/remotbot/voucher.lua  ← Manajemen voucher
            │   └── view/remotbot/
            │       ├── dashboard_status.htm
            │       └── voucher_manager.htm         ← UI kelola voucher
            ├── usr/share/rpcd/acl.d/luci-app-remotbot.json
            └── etc/uci-defaults/luci-app-remotbot
```

---

## 🚀 Instalasi

### 1. Install Paket Utama (Bot + LuCI)

#### Download dari GitHub Releases / Actions

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

#### Build Manual

```sh
git clone https://github.com/irfanFRizki/RemotWRT-Bot
cd RemotWRT-Bot
bash scripts/build-ipk.sh 1.0.0
# Output: dist/*.ipk
```

### 2. Install Tema & Script OpenNDS (Login Voucher)

```sh
# Clone repository
cd /tmp
git clone https://github.com/irfanFRizki/RemotWRT-Bot
cd RemotWRT-Bot/opennds-voucher-theme

# Jalankan installer otomatis
chmod +x install.sh
./install.sh

# Restart OpenNDS
/etc/init.d/opennds restart
```

> **Catatan:** Pastikan OpenNDS sudah terinstall di OpenWrt sebelum menjalankan installer tema.

---

## ⚙️ Konfigurasi

### A. Konfigurasi Telegram Bot

#### Via LuCI (Recommended)

1. Buka LuCI → **Services → Remot Bot → Settings**
2. Isi **Telegram Bot Token** (buat via [@BotFather](https://t.me/BotFather))
3. Isi **Allowed User IDs** (cari via [@userinfobot](https://t.me/userinfobot))
4. Atur notifikasi otomatis (suhu CPU, RAM, WAN, device asing)
5. Pilih bahasa (Indonesia/English)
6. Centang **Enable** → **Save & Apply**
7. Buka **Dashboard → Start**

#### Via UCI (Terminal)

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

### B. Konfigurasi Login Voucher WiFi

#### 1. Buat Voucher via LuCI
1. Buka LuCI → **Services → Remot Bot → Voucher Manager**
2. Pilih kategori: **Keluarga** atau **Pengguna Lain**
3. Masukkan kode voucher dan durasi (menit/jam/hari)
4. Klik **Add Voucher**

#### 2. Tambah IP ke Firewall (Akses Tanpa Login)
IP yang ditambahkan ke daftar putih firewall akan langsung mendapat akses internet tanpa perlu login voucher:
```sh
# Tambah IP ke daftar putih OpenNDS
uci add_list opennds.@opennds[0].preauthenticated_ips='192.168.1.100'
uci commit opennds
/etc/init.d/opennds restart

# Atau tambahkan aturan firewall manual
iptables -I forwarding_rule -s 192.168.1.100 -j ACCEPT
```

#### 3. Custom Voucher (Manual)
Edit file voucher di `/etc/opennds/vouchers.conf`:
```sh
# Format: KODE_VOUCHER|KATEGORI|DURASI_MENIT
FAMILY123|keluarga|1440
GUEST456|pengguna_lain|60
```

#### 4. Halaman Login
Pengguna yang terhubung ke WiFi akan diarahkan ke halaman login dengan:
- Dropdown pilihan: **Keluarga** atau **Pengguna Lain**
- Input kode voucher
- Pesan khusus "WiFi Pribadi tidak dipakai secara umum" untuk kategori Pengguna Lain

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

### Paket Utama (RemotWRT Bot)
| Package | Keterangan |
|---|---|
| `python3-light` | Python runtime minimal |
| `python3-pip` | Package manager Python |
| `python-telegram-bot` | Auto-install via pip saat start |
| `requests` | Auto-install via pip saat start |

### Paket OpenNDS (Login Voucher)
| Package | Keterangan |
|---|---|
| `opennds` | Captive portal daemon |
| `libcurl` | HTTP client untuk autentikasi |
| `uhttpd` | Web server OpenWrt |

> **Catatan:** 
> - Gunakan `--nodeps` saat install remotbot untuk menghindari `python3-multiprocessing` yang sering timeout saat download.
> - Python3 sudah tersedia di OpenWrt 24.10.
> - Pastikan OpenNDS terinstall sebelum mengaktifkan fitur login voucher.

---

## 🔍 Troubleshooting

### Device Tidak Muncul di Dashboard
Jika device sudah connect WiFi tapi tidak muncul di dashboard:
```sh
# Cek status OpenNDS clients
ndsctl clients

# Refresh ARP table
arp -a

# Restart OpenNDS jika perlu
/etc/init.d/opennds restart
```

### Login Voucher Tidak Berfungsi
```sh
# Cek script autentikasi
cat /usr/bin/voucher_auth.sh

# Test manual
echo "FAMILY123|keluarga" | /usr/bin/voucher_auth.sh

# Lihat log OpenNDS
logread | grep opennds
```

### Halaman Login Tidak Muncul
```sh
# Pastikan OpenNDS berjalan
/etc/init.d/opennds status

# Cek konfigurasi theme
uci get opennds.@opennds[0].theme_config

# Restart uhttpd jika perlu
/etc/init.d/uhttpd restart
```

### IP Firewall Tidak Langsung Akses
```sh
# Verifikasi aturan firewall
iptables -L forwarding_rule -n -v

# Cek preauthenticated_ips
uci show opennds | grep preauthenticated

# Flush iptables jika perlu
iptables -F forwarding_rule
```

---

## 👥 Contributors

- [irfanFRizki](https://github.com/irfanFRizki) (Main Developer)
- [agy cli](https://github.com/google-deepmind/antigravity) (AI Assistant / Pair Programmer)

## 📄 License

MIT License — © 2024 [irfanFRizki](https://github.com/irfanFRizki)
