# Integrasi OpenNDS FAS - RemotWRT-Bot

Dokumentasi untuk integrasi captive portal OpenNDS dengan sistem approval via Telegram **dan LuCI Web Interface**.

## File yang Dibuat/Diubah

### File Baru
1. `/usr/bin/fas_server.py` - HTTP server FAS standalone
2. `/etc/init.d/remotbot-fas` - Init script procd untuk FAS server
3. `/etc/config/opennds` - Konfigurasi OpenNDS dengan FAS
4. `/usr/bin/remotbot_actions.py` - Bridge script untuk action approve/block dari LuCI API
5. `/usr/lib/lua/luci/controller/remotbot.lua` - LuCI controller untuk menu RemotWRT-Bot
6. `/usr/lib/lua/luci/controller/api/remotbot_pending.lua` - API endpoint untuk pending approval
7. `/usr/lib/lua/luci/view/remotbot/pending_list.htm` - LuCI web UI untuk manage pending devices

### File Diubah
1. `/usr/bin/pi4Bot.py` - Tambahan handler NDS approve/block
2. `/etc/config/remotbot` - Tambahan opsi FAS (port, pending file, TTL)
3. `Makefile` - Update PKG_RELEASE dan include LuCI files

## Fitur Baru: LuCI Web Interface

### Akses Menu
Setelah install package, akses menu di:
```
http://<openwrt-ip>/cgi-bin/luci/admin/services/remotbot/pending
```

Menu akan muncul di: **Services → RemotWRT-Bot → Pending Approval**

### Fitur Web UI
- **Real-time monitoring**: Auto-refresh setiap 5 detik
- **Statistik**: Counter pending/approved/blocked devices
- **Vendor detection**: Identifikasi vendor device dari MAC OUI (Apple, Samsung, Xiaomi, dll)
- **Action buttons**: Approve/Block langsung dari web interface
- **Dark theme**: Konsisten dengan splash page FAS (neon green/cyan accent)
- **Toast notifications**: Feedback visual setelah action

### API Endpoint

**GET /cgi-bin/luci/admin/services/remotbot/api/pending**
```json
{
  "aa:bb:cc:dd:ee:ff": {
    "status": "pending",
    "ip": "192.168.1.100",
    "hostname": "unknown",
    "timestamp": "2025-01-09T10:30:00Z"
  }
}
```

**POST /cgi-bin/luci/admin/services/remotbot/api/pending/:mac**
```json
{
  "action": "approve"  // atau "block"
}
```

Response:
```json
{
  "success": true,
  "message": "Device approved successfully",
  "mac": "AA:BB:CC:DD:EE:FF",
  "new_status": "approved"
}
```

## Konfigurasi UCI

### remotbot.main (tambahan)
```bash
# Port FAS server (default 2080)
uci set remotbot.main.fas_port='2080'

# File JSON shared untuk status pending
uci set remotbot.main.fas_pending_file='/tmp/opennds_pending.json'

# Throttle notifikasi Telegram (detik)
uci set remotbot.main.fas_notify_ttl='300'

uci commit remotbot
```

### opennds.opennds
```bash
# Aktifkan OpenNDS
uci set opennds.opennds.enabled='1'

# FAS Level 0 (clear text untuk internal network)
uci set opennds.opennds.fas_secure_enabled='0'

# URL FAS server lokal
uci set opennds.opennds.fas_url='http://127.0.0.1:2080/fas'
uci set opennds.opennds.fas_port='2080'

# Block device sebelum auth
uci set opennds.opennds.preauth_idleaction='block'

# Whitelist DNS dan FAS port
uci add_list opennds.opennds.fas_whitelist='tcp 53'
uci add_list opennds.opennds.fas_whitelist='udp 53'
uci add_list opennds.opennds.fas_whitelist='tcp 2080'

uci commit opennds
```

## Instalasi & Start Service

```bash
# 1. Install dependencies
pip3 install requests python-telegram-bot

# 2. Set permission executable
chmod +x /usr/bin/fas_server.py
chmod +x /etc/init.d/remotbot-fas

# 3. Enable & start services
/etc/init.d/remotbot enable
/etc/init.d/remotbot start

/etc/init.d/remotbot-fas enable
/etc/init.d/remotbot-fas start

# 4. Restart OpenNDS (jika sudah terinstall)
/etc/init.d/opennds restart
```

## Testing Plan

### 1. Simulasi Device Baru Connect

**Opsi A: Pakai device fisik**
```bash
# Disconnect device dari WiFi, lalu connect lagi
# Device akan di-redirect ke splash page FAS (port 2080)
```

**Opsi B: Simulasi manual dengan curl**
```bash
# Simulasi request dari OpenNDS ke FAS server
curl -v "http://127.0.0.1:2080/fas?clientip=192.168.1.100&gatewayname=Test&tok=&redir=&authaction=http://192.168.1.1:2080/auth"
```

### 2. Cek Log FAS Server

```bash
# Log realtime
tail -f /var/log/fas_server.log

# Atau via logread
logread | grep fas_server

# Cek status service
/etc/init.d/remotbot-fas status
```

### 3. Verifikasi Pending File

```bash
# Lihat isi pending file
cat /tmp/opennds_pending.json

# Format:
# {
#   "aa:bb:cc:dd:ee:ff": {
#     "status": "pending|approved|blocked",
#     "ip": "192.168.1.100",
#     "hostname": "unknown",
#     "timestamp": 1234567890
#   }
# }
```

### 4. Verifikasi Whitelist Update Setelah Approve

```bash
# Cek UCI whitelist
uci show remotbot.main.mac_whitelist

# Atau
uci get remotbot.main.mac_whitelist
```

### 5. Test Notifikasi Telegram

1. Connect device baru ke jaringan
2. Cek Telegram: harus dapat notifikasi dengan tombol "✅ Setujui" dan "🚫 Blokir"
3. Klik tombol approve → device dapat akses internet
4. Klik tombol block → device ditolak aksesnya

### 6. Test Splash Page

Buka browser di device client, akses http://contoh.com atau http://1.1.1.1
Harus redirect ke splash page dengan:
- Dark theme (background gelap)
- Font Space Mono / DM Sans
- Accent neon green (#00e5a0) atau cyan (#00c8e0)
- Auto-refresh tiap 4 detik (untuk status pending)

## Troubleshooting

### FAS Server tidak jalan
```bash
# Cek log error
logread | grep remotbot-fas

# Manual test
python3 /usr/bin/fas_server.py
```

### Notifikasi Telegram tidak terkirim
```bash
# Verify bot token & allowed users
uci get remotbot.main.bot_token
uci get remotbot.main.allowed_users

# Test koneksi ke Telegram API
curl -s https://api.telegram.org/bot<TOKEN>/getMe
```

### Device tidak redirect ke splash page
```bash
# Cek OpenNDS aktif
/etc/init.d/opennds status

# Cek firewall rule
iptables -L FORWARD -n | grep opennds

# Cek DNS whitelist
uci show opennds.opennds.fas_whitelist
```

### Pending file corrupt
```bash
# Hapus dan restart
rm /tmp/opennds_pending.json
/etc/init.d/remotbot-fas restart
```

## Keamanan

**Catatan penting:**
- `fas_secure_enabled='0'` (clear text) karena ini **internal network**
- Approval manual via Telegram mengurangi risiko unauthorized access
- Untuk public wifi, upgrade ke **FAS Level 1** (hashed token) dengan:
  ```bash
  uci set opennds.opennds.fas_secure_enabled='1'
  ```

## Arsitektur

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Device    │────▶│   OpenNDS    │────▶│  FAS Server │
│   Client    │     │   (Gateway)  │     │  (Port 2080)│
└─────────────┘     └──────────────┘     └─────────────┘
                           │                    │
                           │                    │ (JSON shared file)
                           │                    ▼
                           │           ┌─────────────────┐
                           │           │ /tmp/opennds_   │
                           │           │ pending.json    │
                           │           └─────────────────┘
                           │                    ▲
                           │                    │
                           │              ┌─────────────┐
                           └─────────────▶│  pi4Bot.py  │
                                          │ (Telegram)  │
                                          └─────────────┘
```

## Flow Approval

1. **Device connect** → OpenNDS intercept → Redirect ke FAS server
2. **FAS server** lookup MAC → Cek whitelist → Jika baru, simpan "pending" + kirim Telegram
3. **Admin** terima notifikasi → Klik approve/block di Telegram
4. **pi4Bot.py** update pending file → FAS server detect change → Redirect/deny
5. **Approved**: Device dapat akses internet + MAC ditambahkan ke whitelist (next time auto-approve)
