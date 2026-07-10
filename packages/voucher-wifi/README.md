# 🎫 Sistem Login WiFi Voucher - RemotWRT

Paket lengkap untuk sistem login WiFi voucher berbasis OpenNDS dengan integrasi firewall OpenWRT.

## ✨ Fitur Utama

### 🔐 Sistem Login Voucher
- **Dua Kategori Pengguna:**
  - 👨‍👩‍👧‍👦 **Keluarga**: Memerlukan kode voucher untuk akses
  - 👤 **Pengguna Lain**: Akses langsung dengan pesan "WiFi Pribadi tidak dipakai secara umum"
  
- **Halaman Login Custom**: Desain modern dan responsive
- **Validasi Voucher**: Script autentikasi custom yang fleksibel
- **Logging**: Semua aktivitas login tercatat di `/var/log/voucher_login.log`

### 🛡️ Integrasi Firewall
- **IP Whitelist Otomatis**: IP yang ditambahkan ke whitelist firewall langsung dapat akses internet tanpa login
- **Manajemen via Web Interface**: Tambah/hapus IP whitelist dari dashboard LuCI
- **Persisten Konfigurasi**: Rule firewall tersimpan dan tetap aktif setelah reboot

### 📊 Dashboard LuCI Terintegrasi
- **Voucher Manager**: Kelola voucher keluarga (tambah/hapus)
- **Firewall Whitelist**: Kelola IP yang mendapat akses otomatis
- **Monitoring Client**: Lihat daftar client yang sedang terkoneksi

## 📦 Struktur Paket

```
voucher-wifi/
├── Makefile                          # Build system OpenWRT
├── control/
│   └── control                       # Metadata paket
├── files/
│   ├── etc/
│   │   ├── config/
│   │   │   └── opennds               # Konfigurasi default OpenNDS
│   │   └── opennds/
│   │       └── theme/
│   │           └── login.html        # Halaman login custom
│   ├── usr/
│   │   └── bin/
│   │       └── voucher_auth.sh       # Script autentikasi
│   ├── www/
│   │   └── cgi-bin/
│   │       └── voucher_manager.cgi   # Web interface manajemen
│   └── postinst                      # Script post-installation
└── README.md                         # Dokumentasi ini
```

## 🚀 Instalasi

### Metode 1: Build dari Source (Recommended)

```bash
# Clone repository RemotWRT Bot
cd ~/openwrt
git clone https://github.com/remotwrt/remotwrt-bot.git package/remotwrt-bot

# Build paket
make package/voucher-wifi/compile V=s

# Install ke router
scp bin/packages/*/voucher-wifi/voucher-wifi_1.0.0-1_all.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1 "opkg install /tmp/voucher-wifi_1.0.0-1_all.ipk"
```

### Metode 2: Install Manual (Jika sudah ada file .ipk)

```bash
# Upload file .ipk ke router
scp voucher-wifi_1.0.0-1_all.ipk root@192.168.1.1:/tmp/

# Install via SSH
ssh root@192.168.1.1
opkg update
opkg install /tmp/voucher-wifi_1.0.0-1_all.ipk
```

## ⚙️ Konfigurasi

### A. Konfigurasi OpenNDS

File konfigurasi: `/etc/config/opennds`

```bash
config opennds 'opennds'
    option enabled '1'
    option gatewayinterface 'br-lan'
    option gatewayport '2080'
    option custom_auth_script '/usr/bin/voucher_auth.sh'
    option theme_config '/etc/opennds/theme'
    option clienttimeout '60'
```

Restart OpenNDS setelah perubahan:
```bash
/etc/init.d/opennds restart
```

### B. Manajemen Voucher

#### 1. Via Web Interface (Recommended)
Akses: `http://192.168.1.1/cgi-bin/voucher_manager.cgi`

Fitur:
- ➕ Tambah voucher baru
- 🗑️ Hapus voucher yang ada
- 🔒 Tambah IP ke firewall whitelist
- 📋 Lihat daftar voucher dan IP aktif

#### 2. Via Command Line

**Tambah voucher:**
```bash
echo "KODEVOUCHER123" >> /etc/voucher_keluarga.txt
```

**Lihat voucher yang ada:**
```bash
cat /etc/voucher_keluarga.txt
```

**Hapus voucher:**
```bash
grep -v "KODEVOUCHER123" /etc/voucher_keluarga.txt > /tmp/temp && mv /tmp/temp /etc/voucher_keluarga.txt
```

### C. Firewall Whitelist

#### Via Web Interface:
1. Buka `http://192.168.1.1/cgi-bin/voucher_manager.cgi`
2. Isi IP address di form "Tambah IP ke Firewall Whitelist"
3. Klik "Tambah ke Whitelist"

#### Via Command Line:
```bash
# Tambah IP ke whitelist (akses langsung tanpa login)
iptables -I FORWARD 1 -s 192.168.1.100 -j ACCEPT

# Simpan agar persisten
uci add firewall rule
uci set firewall.@rule[-1].target='ACCEPT'
uci set firewall.@rule[-1].src_ip='192.168.1.100'
uci set firewall.@rule[-1].proto='all'
uci set firewall.@rule[-1].name='Whitelist_Device'
uci commit firewall
/etc/init.d/firewall reload
```

## 🎯 Cara Penggunaan

### Untuk Administrator:

1. **Setup Awal:**
   ```bash
   # Pastikan OpenNDS terinstall
   opkg install opennds
   
   # Install paket voucher-wifi
   opkg install voucher-wifi_1.0.0-1_all.ipk
   ```

2. **Kelola Voucher:**
   - Akses Voucher Manager di browser
   - Tambah voucher untuk keluarga
   - Tambah IP device tertentu ke whitelist jika perlu

3. **Monitor Aktivitas:**
   ```bash
   # Lihat log login realtime
   tail -f /var/log/voucher_login.log
   
   # Cek status client OpenNDS
   ndsctl clients
   ```

### Untuk Pengguna WiFi:

1. **Koneksi ke WiFi:**
   - Pilih network WiFi yang tersedia
   - Browser akan otomatis redirect ke halaman login

2. **Login:**
   - **Keluarga**: Pilih "Keluarga" → Masukkan kode voucher → Klik "Masuk WiFi"
   - **Pengguna Lain**: Pilih "Pengguna Lain" → Langsung klik "Masuk WiFi" (akan muncul peringatan)

3. **Akses Internet:**
   - Setelah login berhasil, internet langsung bisa digunakan
   - Session berlaku sesuai timeout yang dikonfigurasi (default: 60 menit idle)

## 🔧 Troubleshooting

### Masalah: Halaman login tidak muncul
```bash
# Cek status OpenNDS
/etc/init.d/opennds status

# Restart OpenNDS
/etc/init.d/opennds restart

# Cek log error
logread | grep opennds
```

### Masalah: Voucher tidak valid
```bash
# Pastikan voucher ada di file
cat /etc/voucher_keluarga.txt

# Cek script autentikasi
/usr/bin/voucher_auth.sh
# Test manual dengan input simulasi
```

### Masalah: IP whitelist tidak bekerja
```bash
# Cek rule iptables
iptables -L FORWARD -n -v | grep ACCEPT

# Reload firewall
/etc/init.d/firewall reload
```

### Masalah: Client tidak muncul di dashboard
```bash
# Cek client OpenNDS
ndsctl clients

# Cek ARP table
arp -a

# Refresh halaman Voucher Manager
```

## 📝 Voucher Default

Setelah instalasi, tersedia 3 voucher default:
- `KELUARGA123`
- `FAMILY2024`
- `RUMAH456`

**⚠️ Penting**: Ganti voucher default ini dengan voucher Anda sendiri untuk keamanan!

## 📂 File Penting

| File | Deskripsi |
|------|-----------|
| `/etc/voucher_keluarga.txt` | Daftar voucher keluarga aktif |
| `/var/log/voucher_login.log` | Log semua aktivitas login |
| `/etc/config/opennds` | Konfigurasi OpenNDS |
| `/usr/bin/voucher_auth.sh` | Script autentikasi voucher |
| `/www/cgi-bin/voucher_manager.cgi` | Web interface manajemen |

## 🛠️ Development

### Build Package:
```bash
cd ~/openwrt
make package/voucher-wifi/clean
make package/voucher-wifi/compile V=s
```

### Testing Script Auth:
```bash
# Simulasi input ke script auth
echo -e "fasid\norigurl\nredirurl\ntok\nkeluarga:KELUARGA123\n" | /usr/bin/voucher_auth.sh
```

## 📄 License

MIT License - RemotWRT Team

## 🤝 Kontribusi

Silakan fork dan submit pull request ke:
https://github.com/remotwrt/remotwrt-bot

## 📞 Support

- GitHub Issues: https://github.com/remotwrt/remotwrt-bot/issues
- Email: support@remotwrt.com

---

**© 2024 RemotWRT Bot. All rights reserved.**
