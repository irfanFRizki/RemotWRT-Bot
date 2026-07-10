#!/bin/sh
# Script Autentikasi Voucher WiFi untuk OpenNDS
# Lokasi: /usr/bin/voucher_auth.sh

# Fungsi untuk logging
log_auth() {
    logger -t "voucher_auth" "$1"
}

# Baca input dari stdin (diberikan oleh OpenNDS)
read fasid
read origurl
read redirurl
read tok
read username
read password

# Ekstrak kategori dan voucher dari username (format: KATEGORIA:VOUCHER)
# Atau jika hanya kategori (untuk pengguna lain)
CATEGORY=$(echo "$username" | cut -d':' -f1)
VOUCHER=$(echo "$username" | cut -d':' -f2)

# Jika tidak ada pemisah :, anggap seluruh username adalah kategori
if [ "$CATEGORY" = "$username" ]; then
    VOUCHER=""
fi

# Dapatkan IP dan MAC client dari environment variable OpenNDS
CLIENT_IP="${ip}"
CLIENT_MAC="${mac}"

log_auth "Login attempt - Category: $CATEGORY, Voucher: $VOUCHER, IP: $CLIENT_IP, MAC: $CLIENT_MAC"

# Cek apakah IP sudah ada di firewall whitelist (zone trusted)
# Menggunakan iptables untuk cek apakah IP ada di chain ACCEPT khusus
check_firewall_whitelist() {
    local ip=$1
    # Cek di chain forward atau input apakah IP ini sudah di-ACCEPT
    if iptables -L FORWARD -n -v | grep -q "$ip"; then
        return 0
    fi
    return 1
}

# Fungsi validasi voucher keluarga
validate_keluarga_voucher() {
    local voucher=$1
    
    # Daftar voucher keluarga (bisa ditambah/diedit via LuCI)
    # Format: satu voucher per baris di file /etc/voucher_keluarga.txt
    if [ -f /etc/voucher_keluarga.txt ]; then
        if grep -qx "$voucher" /etc/voucher_keluarga.txt; then
            return 0
        fi
    fi
    
    # Fallback: voucher hardcoded untuk testing
    case "$voucher" in
        "KELUARGA123"|"FAMILY2024"|"RUMAH456")
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Fungsi untuk pengguna lain (tanpa voucher, tapi dengan peringatan)
validate_pengguna_lain() {
    # Untuk pengguna lain, kita izinkan tapi dengan logging khusus
    log_auth "Pengguna Lain login - IP: $CLIENT_IP - WiFi Pribadi tidak dipakai secara umum"
    return 0
}

# Proses autentikasi
authenticate() {
    case "$CATEGORY" in
        "keluarga")
            if [ -z "$VOUCHER" ]; then
                log_auth "FAILED - Keluarga tanpa voucher"
                echo "0"
                exit 0
            fi
            
            if validate_keluarga_voucher "$VOUCHER"; then
                log_auth "SUCCESS - Keluarga dengan voucher: $VOUCHER"
                echo "1"
                
                # Tambahkan ke log sukses
                echo "$(date '+%Y-%m-%d %H:%M:%S') - $CLIENT_MAC ($CLIENT_IP) - Keluarga - $VOUCHER" >> /var/log/voucher_login.log
                
                exit 0
            else
                log_auth "FAILED - Voucher keluarga tidak valid: $VOUCHER"
                echo "0"
                exit 0
            fi
            ;;
            
        "pengguna_lain")
            if validate_pengguna_lain; then
                log_auth "SUCCESS - Pengguna Lain (WiFi Pribadi)"
                echo "1"
                
                # Tambahkan ke log
                echo "$(date '+%Y-%m-%d %H:%M:%S') - $CLIENT_MAC ($CLIENT_IP) - Pengguna Lain" >> /var/log/voucher_login.log
                
                exit 0
            else
                log_auth "FAILED - Pengguna Lain ditolak"
                echo "0"
                exit 0
            fi
            ;;
            
        *)
            log_auth "FAILED - Kategori tidak dikenali: $CATEGORY"
            echo "0"
            exit 0
            ;;
    esac
}

# Jalankan autentikasi
authenticate
