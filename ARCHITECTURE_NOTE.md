# Arsitektur Autentikasi & Monitoring — RemotWRT-Bot

Dokumen ini menjelaskan pembagian peran dalam sistem autentikasi captive portal WiFi dan monitoring Telegram.

## 1. Single Source of Truth Autentikasi (BinAuth)

Satu-satunya mekanisme autentikasi resmi untuk captive portal OpenNDS adalah **BinAuth** yang berjalan melalui script autentikasi:
`packages/voucher-wifi/files/usr/bin/voucher_auth.sh`

Konfigurasi OpenNDS harus merujuk ke script ini melalui opsi:
```
option custom_auth_script '/usr/bin/voucher_auth.sh'
```

### Mengapa BinAuth?
- Dieksekusi langsung oleh daemon `opennds` dalam konteks **root** — memiliki hak akses penuh untuk memanggil `iptables` via `remotwrt_firewall_helper.sh` tanpa masalah permission.
- Mendukung validasi voucher (Keluarga / Pengguna Lain) secara lokal dan instan.
- Satu titik kebenaran yang deterministik — tidak bergantung pada service lain yang mungkin tidak berjalan.

### Siapa pemilik `/etc/config/opennds`?
Paket `voucher-wifi` adalah satu-satunya pemilik konfigurasi OpenNDS. Paket `remotbot` **tidak boleh** menyertakan atau memodifikasi file `/etc/config/opennds`.

---

## 2. Status FAS Server dan Telegram Pending-Approval

> [!IMPORTANT]
> **Pernyataan Arsitektur Utama:** Satu-satunya mekanisme auth captive portal adalah BinAuth via voucher_auth.sh. FAS server & pending-approval Telegram adalah fitur monitoring/override terpisah, tidak menentukan akses internet device baru.

FAS Server (`fas_server.py`) dan fitur pending-approval Telegram (`remotbot_pending.lua`) **tidak lagi menjadi mekanisme autentikasi utama captive portal** sejak sistem voucher (BinAuth) diaktifkan.

### Status sekarang:
- **Monitoring & Override Manual saja:** Admin bisa memantau perangkat terhubung atau melakukan tindakan manual (blokir MAC address) via Telegram/LuCI.
- **Tidak menangani alur login tamu:** Semua client baru harus melalui login portal BinAuth menggunakan voucher.
- **Tidak lagi terdaftar sebagai `fas_url` di OpenNDS:** Service `remotbot-fas` tidak lagi dikonfigurasi sebagai FAS endpoint OpenNDS. Service ini boleh tetap berjalan untuk fitur admin override, tapi tidak menentukan akses internet device baru.
- **Berjalan sebagai non-root:** Daemon `remotbot-fas` berjalan sebagai user `remotbot` (non-root) — tidak bisa langsung panggil `iptables`. Blokir MAC dari Telegram harusnya selalu lewat `remotwrt_firewall_helper.sh` yang dieksekusi terpisah (single source of truth round 3).

---

## 3. Aturan Instalasi dan Urutan Package

Untuk memastikan tidak terjadi konflik konfigurasi, terlepas dari urutan instalasi:

| Aturan | Detail |
|---|---|
| Pemilik `/etc/config/opennds` | Hanya `voucher-wifi` |
| `remotbot` DEPENDS | `+voucher-wifi` (wajib, agar konfigurasi BinAuth yang terinstall terakhir) |
| `voucher-wifi` DEPENDS | `+iptables` (di OpenWrt 24.10+ otomatis di-resolve ke `iptables-nft` compat layer) |

### Simulasi urutan install:
- **remotbot dulu → voucher-wifi:** Karena `remotbot` DEPENDS `+voucher-wifi`, package manager akan install `voucher-wifi` lebih dulu, lalu `remotbot`. `/etc/config/opennds` milik `voucher-wifi` terpasang, `remotbot` tidak menyentuhnya.
- **voucher-wifi dulu → remotbot:** `/etc/config/opennds` sudah terpasang oleh `voucher-wifi`. `remotbot` tidak punya file config opennds sama sekali, jadi tidak akan menimpa.

**Kedua urutan → `/etc/config/opennds` selalu berisi `custom_auth_script`.**

---

## 4. Alur Iptables dan Privilege

```
OpenNDS (root)
  └── voucher_auth.sh (dipanggil oleh opennds, berjalan sebagai root)
        └── remotwrt_firewall_helper.sh grant/revoke (iptables, root) ✅

remotbot/remotbot-fas (user: remotbot, non-root)
  └── Override manual admin → memanggil remotwrt_firewall_helper.sh
        (hanya jika dikonfigurasi lewat sudo wrapper atau setuid) ⚠️
```

Catatan: Untuk fitur blokir-MAC via Telegram (`pi4Bot.py`), pastikan memanggil `remotwrt_firewall_helper.sh` lewat mekanisme yang punya hak root (sudo wrapper atau OpenWrt procd dengan privilege yang tepat), bukan langsung dari proses `remotbot` yang berjalan sebagai non-root.
