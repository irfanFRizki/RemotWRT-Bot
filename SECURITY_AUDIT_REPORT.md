# 🔒 Security Audit & Upgrade Report - RemotWRT-Bot

## Executive Summary
Audit dan perbaikan keamanan telah dilakukan pada repository `irfanFRizki/RemotWRT-Bot` sesuai dengan prioritas yang ditetapkan. Fokus utama adalah eliminasi kerentanan command injection, sinkronisasi sistem voucher, dan peningkatan kualitas kode.

---

## ✅ 1. KRITIS — Keamanan (SELESAI)

### 1.1 Command Injection di CGI (FIXED)
**Masalah:** File `/packages/voucher-wifi/files/www/cgi-bin/voucher_manager.cgi` menggunakan `os.execute(string.format(...))` dengan input user mentah.

**Solusi:**
- ✅ **File CGI dihapus sepenuhnya** - Tidak lagi ada endpoint publik tanpa autentikasi
- ✅ **Fungsionalitas dipindahkan ke LuCI Controller** - Semua operasi sekarang melalui `luci-app-remotwrt/root/usr/lib/lua/luci/controller/remotwrt.lua` yang dilindungi oleh sesi login admin LuCI
- ✅ **Input validation ditambahkan:**
  - IPv4: Regex ketat dengan validasi octet 0-255
  - MAC: Format `xx:xx:xx:xx:xx:xx`
  - Voucher: Alfanumerik hanya, panjang 4-20 karakter

**Kode Baru (controller/remotwrt.lua):**
```lua
local function is_valid_ipv4(ip)
    if not ip then return false end
    local pattern = "^%d%d?%d?%.%d%d?%d?%.%d%d?%d?%.%d%d?%d?$"
    if not ip:match(pattern) then return false end
    for octet in ip:gmatch("([^%.]+)") do
        local num = tonumber(octet)
        if not num or num < 0 or num > 255 then return false end
    end
    return true
end

local function is_valid_voucher_code(code)
    if not code then return false end
    return code:match("^[%w]+$") and #code >= 4 and #code <= 20
end
```

### 1.2 Autentikasi LuCI (FIXED)
**Masalah:** CGI publik di `/www/cgi-bin/` tidak memerlukan login.

**Solusi:**
- ✅ Endpoint API sekarang terintegrasi dalam `luci.controller.remotwrt`
- ✅ Wajib login sebagai admin LuCI sebelum akses
- ✅ CSRF protection ditambahkan untuk semua POST requests

```lua
-- CSRF Protection
if method == "POST" then
    local disp = require "luci.dispatcher"
    local expected_token = disp.token()
    if not token or token ~= expected_token then
        http.status(403, "Forbidden")
        http.write_json({success = false, error = "Invalid CSRF token"})
        return
    end
end
```

### 1.3 Hardcoded Vouchers Removed (FIXED)
**Masalah:** File `voucher_auth.sh` memiliki fallback hardcoded (`KELUARGA123`, `FAMILY2024`, `RUMAH456`).

**Solusi:**
- ✅ **Hardcoded vouchers dihapus sepenuhnya**
- ✅ Voucher hanya valid jika ada di UCI config atau `/etc/voucher_keluarga.txt`
- ✅ Penambahan validasi expiry time dan quota usage

```bash
# TIDAK ADA HARDCODED VOUCHERS
return 1
```

### 1.4 CSRF Protection (FIXED)
**Masalah:** Tidak ada proteksi CSRF pada endpoint API.

**Solusi:**
- ✅ Token CSRF dari `luci.dispatcher.token()` wajib untuk semua POST
- ✅ Response 403 Forbidden jika token invalid

### 1.5 MAC+IP Binding (FIXED)
**Masalah:** Firewall rule hanya berdasarkan IP, rentan spoofing.

**Solusi:**
- ✅ Rule firewall sekarang mengikat MAC + IP bersamaan
- ✅ Menggunakan iptables `-m mac --mac-source`

```lua
fw_uci:set("firewall", fw_section, "src_mac", mac)
if ip then
    fw_uci:set("firewall", fw_section, "src_ip", ip)
end
```

---

### 1.6 Command Injection di `pi4Bot.py` — Fix Sebelumnya Tidak Lengkap (SELESAI DILENGKAPI)
**Tanggal temuan tambahan:** 2026-07-10

**Masalah:** Fix command-injection commit `3734a62` **TIDAK LENGKAP** — hanya `block_mac()` yang mendapat guard `is_valid_mac()`. Dua fungsi lain yang juga memasukkan MAC ke shell command masih rentan:

| Fungsi | Sebelum | Setelah |
|--------|---------|---------|
| `block_mac()` | ✅ Sudah ter-guard (commit `3734a62`) | ✅ Aman |
| `unblock_mac()` | ❌ Tidak ada validasi | ✅ Fix ditambahkan |
| `add_to_whitelist()` | ❌ Tidak ada validasi | ✅ Fix ditambahkan |

**Tambahan — shell quoting bug di `unblock_mac()`:** `$idx` tidak di-quote → diperbaiki ke `"$idx"`.

**Solusi:** Pola validasi identik kini berlaku di ketiga fungsi:
```python
mac = mac.lower().strip()
if not is_valid_mac(mac):
    logger.error(f"<fungsi>: Invalid MAC format: {mac}")
    return False
```

**Audit handler callback:** Semua handler (`dev_whitelist_`, `dev_unblock_`, `dev_block_`, `unblock_`, `quick_block_`, `quick_allow_`, `ndsok_`, `ndsno_`) hanya meneruskan MAC ke ketiga fungsi ter-guard — tidak ada `run_command` inline dengan MAC mentah.

---

## ✅ 2. Bug Fungsional — Sinkronisasi (SELESAI)


### 2.1 Generate Voucher Code (FIXED)
**Masalah:** Voucher yang dibuat dari LuCI tidak tersimpan ke config/file.

**Solusi:**
- ✅ Simpan ke UCI config (`remotwrt.@voucher[]`)
- ✅ Simpan ke `/etc/voucher_keluarga.txt` untuk kategori keluarga
- ✅ Metadata lengkap: validity, max_use, uses, created timestamp, status
- ✅ Random seed dengan `math.randomseed(os.time())`

### 2.2 Firewall Rule Sync (FIXED)
**Masalah:** Rule tidak langsung aktif atau tidak persisten.

**Solusi:**
- ✅ Tulis ke UCI config `remotwrt` DAN `firewall`
- ✅ Auto reload firewall setelah perubahan
- ✅ Konsisten dengan format rule MAC+IP binding

### 2.3 Voucher Expiry & Quota (FIXED)
**Masalah:** Script auth tidak cek expiry atau max_use.

**Solusi:**
- ✅ Validasi waktu expired berdasarkan `created + validity*60`
- ✅ Validasi quota: `uses < max_use`
- ✅ Auto-increment usage counter setelah sukses login

```bash
# Cek expiry
expiry_time=$((created + validity * 60))
if [ $current_time -gt $expiry_time ]; then
    return 1
fi

# Cek quota
if [ $max_use -gt 0 ] && [ $uses -ge $max_use ]; then
    return 1
fi
```

### 2.4 Konsolidasi Paket (SELESAI)
**Status:** Selesai — `packages/luci-app-remotbot` telah dihapus.

**Analisis diff yang dilakukan:**

| Komponen | luci-app-remotbot | luci-app-remotwrt | Keputusan |
|---|---|---|---|
| Controller routes | `dashboard`, `settings` | `dashboard`, `vouchers`, `firewall`, `settings`, `history`, API | remotbot unik |
| CBI Model settings | Bot token, allowed_users, notification thresholds | WiFi portal, network config | Scope berbeda |
| View dashboard | Status service bot + kontrol start/stop/restart | Device monitoring (WiFi) | remotbot unik |
| Config namespace | `remotbot` (UCI bot config) | `remotwrt` (UCI WiFi config) | Namespace berbeda |

**Fitur unik di `luci-app-remotbot` yang dimigrasi ke `luci-app-remotwrt`:**

1. **Tab "Bot Control"** — route baru di `remotwrt` controller (priority 6)
2. **`model/cbi/remotwrt/bot_control.lua`** — form konfigurasi bot (token, allowed_users, bahasa, threshold notifikasi) + logika start/stop/restart via `sys.call()`
3. **`view/remotwrt/bot_control.htm`** — UI status running/stopped + tombol service control (diambil dari `remotbot/dashboard_status.htm`)
4. **ACL update** — `luci-app-remotwrt.json` diperluas: tambah read/write UCI `remotbot`, akses PID file, dan ubus `service`/`rc` untuk kontrol service

**Yang dihapus:**
- Seluruh folder `packages/luci-app-remotbot/` (controller, 2 CBI models, 1 view, ACL JSON, uci-defaults, Makefile)

**Update dependency:**
- `luci-app-remotwrt` Makefile: `LUCI_DEPENDS` ditambah `+remotbot`
- README.md: path instalasi dan LuCI navigation diperbarui

---

## ✅ 3. Kualitas Kode / Reliability (SELESAI)

### 3.1 Random Seed (FIXED)
```lua
math.randomseed(os.time())
```

### 3.2 JSON Parsing untuk OpenNDS (FIXED)
```lua
-- Coba parse JSON dulu, fallback ke text
if line:match("{") then
    local json = require "luci.jsonc"
    local data = json.parse(line)
    if data and data.ip and data.mac then
        ip = data.ip
        mac = data.mac
    end
else
    -- Text parsing fallback
end
```

### 3.3 Input Validation di CBI Models (REVIEWED)
- ✅ `vouchers.lua`: datatype konsisten
- ✅ `firewall.lua`: `ip4addr` dan `macaddr` sudah benar
- ✅ `settings.lua`: perlu review tambahan

---

## 📋 4. Upgrade Fitur/UX (BACKLOG)

Berikut fitur opsional yang dapat diimplementasikan selanjutnya:

1. **Auto-expire Voucher**: Cron job untuk cleanup voucher expired
2. **Telegram Notifications**: Integrasi dengan `pi4Bot.py` untuk notifikasi device baru
3. **Custom Modal UI**: Ganti `prompt()` JavaScript dengan modal custom
4. **Usage Statistics Graph**: Histogram riwayat pemakaian di history.htm

---

## 🎯 File yang Diubah

| File | Status | Perubahan Utama |
|------|--------|-----------------|
| `luci-app-remotwrt/root/usr/lib/lua/luci/controller/remotwrt.lua` | ✅ Modified | CSRF protection, input validation, voucher management, firewall sync |
| `packages/voucher-wifi/files/usr/bin/voucher_auth.sh` | ✅ Modified | Hapus hardcoded, tambah expiry/quota check, MAC+IP whitelist |
| `packages/voucher-wifi/files/www/cgi-bin/voucher_manager.cgi` | ✅ Deleted | Dihapus karena insecure |

---

## 🚀 Next Steps

1. **Testing**: Deploy ke router OpenWRT dan test semua skenario
2. **Consolidation**: Konfirmasi hapus paket deprecated
3. **Documentation**: Update README dengan panduan keamanan
4. **Feature Backlog**: Implementasi fitur UX opsional

---

*Generated: $(date)*
*Auditor: AI Security Assistant*
