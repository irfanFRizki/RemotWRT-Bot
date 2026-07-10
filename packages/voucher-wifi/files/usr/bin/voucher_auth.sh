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

# Cek apakah IP+MAC sudah ada di firewall whitelist
check_firewall_whitelist() {
    local ip=$1
    local mac=$2
    
    # Cek di iptables apakah IP+MAC ini sudah di-ACCEPT
    if iptables -L forwarding_rule -n -v 2>/dev/null | grep -q "$ip.*$mac"; then
        return 0
    fi
    
    if iptables -L FORWARD -n -v 2>/dev/null | grep -q "$ip.*$mac"; then
        return 0
    fi
    
    return 1
}

# Fungsi validasi voucher keluarga dengan checking expiry dan quota
# Support field "permanent" - jika permanent=1, skip pengecekan expiry
validate_keluarga_voucher() {
    local voucher=$1
    local current_time=$(date +%s)
    
    # Prioritas: cek dari UCI config terlebih dahulu
    if command -v uci >/dev/null 2>&1 && [ -f /etc/config/remotwrt ]; then
        local found=0
        
        for section in $(uci show remotwrt 2>/dev/null | grep '=voucher' | cut -d'.' -f2 | cut -d'=' -f1); do
            local code=$(uci get remotwrt.@voucher["$section"].code 2>/dev/null)
            if [ "$code" = "$voucher" ]; then
                found=1
                local validity=$(uci get remotwrt.@voucher["$section"].validity 2>/dev/null || echo "60")
                local max_use=$(uci get remotwrt.@voucher["$section"].max_use 2>/dev/null || echo "1")
                local uses=$(uci get remotwrt.@voucher["$section"].uses 2>/dev/null || echo "0")
                local created=$(uci get remotwrt.@voucher["$section"].created 2>/dev/null || echo "0")
                local status=$(uci get remotwrt.@voucher["$section"].status 2>/dev/null || echo "active")
                local permanent=$(uci get remotwrt.@voucher["$section"].permanent 2>/dev/null || echo "0")
                
                # Cek status
                if [ "$status" != "active" ]; then
                    log_auth "FAILED - Voucher status not active: $status"
                    return 1
                fi
                
                # Cek expiry - SKIP JIKA permanent=1
                # permanent=1 berarti akses selamanya, tidak ada expiry
                # max_use tetap dicek meskipun permanent (untuk limit device sharing)
                if [ "$permanent" != "1" ] && [ $validity -gt 0 ] && [ $created -gt 0 ]; then
                    local expiry_time=$((created + validity * 60))
                    if [ $current_time -gt $expiry_time ]; then
                        log_auth "FAILED - Voucher expired"
                        return 1
                    fi
                fi
                
                # Cek quota (tetap berlaku untuk permanent voucher)
                if [ $max_use -gt 0 ] && [ $uses -ge $max_use ]; then
                    log_auth "FAILED - Max use reached ($uses/$max_use)"
                    return 1
                fi
                
                return 0
            fi
        done
    fi
    
    # Fallback: cek dari file teks (tanpa support permanent)
    if [ -f /etc/voucher_keluarga.txt ]; then
        if grep -qx "$voucher" /etc/voucher_keluarga.txt; then
            return 0
        fi
    fi
    
    # TIDAK ADA HARDCODED VOUCHERS
    return 1
}

# Increment usage counter
increment_voucher_usage() {
    local voucher=$1
    
    if command -v uci >/dev/null 2>&1 && [ -f /etc/config/remotwrt ]; then
        for section in $(uci show remotwrt 2>/dev/null | grep '=voucher' | cut -d'.' -f2 | cut -d'=' -f1); do
            local code=$(uci get remotwrt.@voucher["$section"].code 2>/dev/null)
            if [ "$code" = "$voucher" ]; then
                local uses=$(uci get remotwrt.@voucher["$section"].uses 2>/dev/null || echo "0")
                uci set remotwrt.@voucher["$section"].uses="$((uses + 1))"
                uci commit remotwrt
                break
            fi
        done
    fi
}

# Validasi pengguna lain - SEKARANG WAJIB VOUCHER (tidak ada lagi jalur tanpa kode)
validate_pengguna_lain_voucher() {
    local voucher=$1
    local current_time=$(date +%s)
    
    # Cek dari UCI config untuk voucher category=pengguna_lain
    if command -v uci >/dev/null 2>&1 && [ -f /etc/config/remotwrt ]; then
        for section in $(uci show remotwrt 2>/dev/null | grep '=voucher' | cut -d'.' -f2 | cut -d'=' -f1); do
            local code=$(uci get remotwrt.@voucher["$section"].code 2>/dev/null)
            local cat=$(uci get remotwrt.@voucher["$section"].category 2>/dev/null)
            if [ "$code" = "$voucher" ] && [ "$cat" = "pengguna_lain" ]; then
                local validity=$(uci get remotwrt.@voucher["$section"].validity 2>/dev/null || echo "60")
                local max_use=$(uci get remotwrt.@voucher["$section"].max_use 2>/dev/null || echo "1")
                local uses=$(uci get remotwrt.@voucher["$section"].uses 2>/dev/null || echo "0")
                local created=$(uci get remotwrt.@voucher["$section"].created 2>/dev/null || echo "0")
                local status=$(uci get remotwrt.@voucher["$section"].status 2>/dev/null || echo "active")
                
                # Cek status
                if [ "$status" != "active" ]; then
                    log_auth "FAILED - Voucher status not active: $status"
                    return 1
                fi
                
                # Cek expiry (guest tidak pernah permanent)
                if [ $validity -gt 0 ] && [ $created -gt 0 ]; then
                    local expiry_time=$((created + validity * 60))
                    if [ $current_time -gt $expiry_time ]; then
                        log_auth "FAILED - Voucher expired"
                        return 1
                    fi
                fi
                
                # Cek quota
                if [ $max_use -gt 0 ] && [ $uses -ge $max_use ]; then
                    log_auth "FAILED - Max use reached ($uses/$max_use)"
                    return 1
                fi
                
                return 0
            fi
        done
    fi
    
    # Tidak ada fallback ke hardcoded atau bypass
    log_auth "FAILED - Voucher pengguna_lain tidak ditemukan: $voucher"
    return 1
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
                log_auth "SUCCESS - Keluarga: $VOUCHER"
                echo "1"
                increment_voucher_usage "$VOUCHER"
                echo "$(date '+%Y-%m-%d %H:%M:%S') - $CLIENT_MAC ($CLIENT_IP) - Keluarga - $VOUCHER" >> /var/log/voucher_login.log
                exit 0
            else
                log_auth "FAILED - Voucher tidak valid/expired: $VOUCHER"
                echo "0"
                exit 0
            fi
            ;;
            
        "pengguna_lain")
            if [ -z "$VOUCHER" ]; then
                log_auth "FAILED - Pengguna Lain tanpa voucher"
                echo "0"
                exit 0
            fi
            
            if validate_pengguna_lain_voucher "$VOUCHER"; then
                log_auth "SUCCESS - Pengguna Lain: $VOUCHER"
                echo "1"
                increment_voucher_usage "$VOUCHER"
                echo "$(date '+%Y-%m-%d %H:%M:%S') - $CLIENT_MAC ($CLIENT_IP) - Pengguna Lain - $VOUCHER" >> /var/log/voucher_login.log
                exit 0
            else
                log_auth "FAILED - Voucher pengguna_lain tidak valid/expired: $VOUCHER"
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

# Cek firewall whitelist terlebih dahulu (bypass login)
if check_firewall_whitelist "$CLIENT_IP" "$CLIENT_MAC"; then
    log_auth "AUTO-APPROVED - IP+MAC dalam whitelist: $CLIENT_IP ($CLIENT_MAC)"
    echo "1"
    exit 0
fi

# Jalankan autentikasi
authenticate
