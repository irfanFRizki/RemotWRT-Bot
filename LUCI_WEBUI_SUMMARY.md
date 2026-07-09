# LuCI Web Interface untuk Pending Approval - Summary

## Yang Baru Ditambahkan

### 1. LuCI Controller (`luasrc/controller/remotbot.lua`)
- Menu **Services → RemotWRT-Bot → Pending Approval**
- Routing ke template view dan API endpoint

### 2. API Controller (`luasrc/controller/api/remotbot_pending.lua`)
- `GET /admin/services/remotbot/api/pending` - Baca semua pending entries
- `POST /admin/services/remotbot/api/pending/:mac` - Approve/Block device
- Integrasi dengan UCI config untuk path file pending
- Atomic write dengan file locking

### 3. Bridge Script (`files/usr/bin/remotbot_actions.py`)
- CLI script untuk approve/block dari LuCI API
- Fungsi sama dengan yang di pi4Bot.py (nds_approve/nds_block)
- Handle:
  - Update status di JSON pending file
  - Tambah MAC ke whitelist UCI (untuk approve)
  - Blokir via iptables (untuk block)
- Atomic read/write dengan fcntl locking

### 4. Web UI Template (`luasrc/view/remotbot/pending_list.htm`)
- Dark theme (konsisten dengan splash page FAS)
- Auto-refresh 5 detik
- Statistik real-time (pending/approved/blocked)
- Vendor detection dari MAC OUI
- Toast notifications untuk feedback
- Responsive design

### 5. Updated Makefile
- PKG_RELEASE: 1 → 2
- Include LuCI files dalam package install
- Dependencies tetap sama

## Cara Pakai

### Via Web Browser
1. Buka `http://<openwrt-ip>/cgi-bin/luci/admin/services/remotbot/pending`
2. Lihat daftar device pending
3. Klik "✓ Approve" atau "✕ Block"
4. Device langsung dapat akses (approve) atau ditolak (block)
5. MAC otomatis ditambahkan ke whitelist jika approve

### Via API (curl)
```bash
# List semua pending
curl -s http://localhost/cgi-bin/luci/admin/services/remotbot/api/pending | jq

# Approve device
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"action":"approve"}' \
  http://localhost/cgi-bin/luci/admin/services/remotbot/api/pending/AA:BB:CC:DD:EE:FF

# Block device
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"action":"block"}' \
  http://localhost/cgi-bin/luci/admin/services/remotbot/api/pending/AA:BB:CC:DD:EE:FF
```

### Via CLI Script
```bash
# Approve
/usr/bin/remotbot_actions.py AA:BB:CC:DD:EE:FF approve

# Block
/usr/bin/remotbot_actions.py AA:BB:CC:DD:EE:FF block
```

## Arsitektur Lengkap

```
┌─────────────────┐
│   LuCI Browser  │
│   (Web UI)      │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│ LuCI Controller │
│ (Lua)           │
└────────┬────────┘
         │ Call Python script
         ▼
┌─────────────────┐     ┌──────────────┐
│ remotbot_       │────▶│ JSON Pending │
│ actions.py      │     │ File         │
└────────┬────────┘     └──────────────┘
         │
         ├─▶ UCI whitelist (approve)
         └─▶ iptables rules (block)

┌─────────────────┐     ┌──────────────┐
│ Telegram Bot    │◀───▶│ JSON Pending │
│ (pi4Bot.py)     │     │ File         │
└─────────────────┘     └──────────────┘
                               ▲
                               │
                        ┌──────┴──────┐
                        │ fas_server.py│
                        │ (FAS HTTP)   │
                        └─────────────┘
```

## Keamanan

- **File locking**: Mencegah race condition saat multiple access
- **Atomic write**: Temp file + rename untuk data integrity
- **MAC validation**: Basic format check sebelum proses
- **Same source of truth**: Semua pakai file JSON yang sama (`/tmp/opennds_pending.json`)

## Testing Checklist

- [ ] Menu muncul di LuCI (Services → RemotWRT-Bot)
- [ ] Halaman pending list bisa diakses
- [ ] Auto-refresh jalan (cek network tab browser)
- [ ] Statistik counter update real-time
- [ ] Vendor detection jalan (Apple/Samsung/Xiaomi/etc)
- [ ] Approve button → device dapat akses + masuk whitelist
- [ ] Block button → device ditolak + iptables rule
- [ ] Toast notification muncul setelah action
- [ ] API endpoint bisa diakses via curl
- [ ] remotbot_actions.py bisa dijalankan manual
