#!/bin/sh
# remotwrt_firewall_helper.sh - Single source of truth for firewall grant/revoke
# Called by: voucher_auth.sh, controller/remotwrt.lua, session_cleanup.sh
# Location: /usr/bin/remotwrt_firewall_helper.sh

set -e

LOG_FILE="/var/log/voucher_login.log"
TRACKING_DIR="/tmp/remotwrt_sessions"

log_fw() {
    logger -t "remotwrt_fw" "$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - FIREWALL - $1" >> "$LOG_FILE"
}

usage() {
    echo "Usage: $0 <grant|revoke> <MAC> <IP> [permanent:0|1] [expiry_epoch]"
    echo ""
    echo "Commands:"
    echo "  grant <MAC> <IP> <permanent> <expiry_epoch>  - Add firewall rule"
    echo "  revoke <MAC> <IP>                            - Remove firewall rule"
    echo ""
    echo "Parameters:"
    echo "  MAC          - MAC address (format: AA:BB:CC:DD:EE:FF)"
    echo "  IP           - IP address (format: 192.168.1.100)"
    echo "  permanent    - 1 for permanent rule, 0 for temporary"
    echo "  expiry_epoch - Unix timestamp when session expires (ignored if permanent=1)"
    exit 1
}

# Validate MAC address format
validate_mac() {
    local mac="$1"
    if ! echo "$mac" | grep -qE "^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"; then
        log_fw "ERROR: Invalid MAC format: $mac"
        return 1
    fi
    return 0
}

# Validate IP address format
validate_ip() {
    local ip="$1"
    if ! echo "$ip" | grep -qE "^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$"; then
        log_fw "ERROR: Invalid IP format: $ip"
        return 1
    fi
    return 0
}

# Grant access: add iptables rule and optionally track session
grant_access() {
    local mac="$1"
    local ip="$2"
    local permanent="$3"
    local expiry="$4"
    
    validate_mac "$mac" || return 1
    validate_ip "$ip" || return 1
    
    # Normalize MAC to uppercase
    mac=$(echo "$mac" | tr 'a-f' 'A-F')
    
    # Add iptables rule immediately (for both permanent and temporary)
    # Using forwarding_rule chain (OpenWRT standard)
    if ! iptables -L forwarding_rule -n 2>/dev/null | grep -q "$ip.*$mac"; then
        iptables -I forwarding_rule -m mac --mac-source "$mac" -j ACCEPT 2>/dev/null || \
        iptables -I FORWARD -m mac --mac-source "$mac" -j ACCEPT 2>/dev/null || true
        log_fw "GRANT: Added iptables rule for MAC=$mac IP=$ip"
    fi
    
    if [ "$permanent" = "1" ]; then
        # Permanent rule: add to UCI firewall config for persistence across reboots
        local fw_name="RemotWRT_permanent_${mac//:/}"
        
        if command -v uci >/dev/null 2>&1; then
            # Check if rule already exists
            if ! uci get firewall."$fw_name" >/dev/null 2>&1; then
                uci add firewall rule
                local new_section=$(uci show firewall | grep "=rule" | tail -1 | cut -d'.' -f2 | cut -d'=' -f1)
                uci set firewall."$new_section".name="$fw_name"
                uci set firewall."$new_section".target="ACCEPT"
                uci set firewall."$new_section".src="lan"
                uci set firewall."$new_section".proto="all"
                uci set firewall."$new_section".src_mac="$mac"
                uci set firewall."$new_section".comment="Permanent access via RemotWRT voucher"
                uci commit firewall
                log_fw "GRANT PERMANENT: Added UCI rule $fw_name for MAC=$mac"
            fi
        fi
        
        # No tracking file needed for permanent sessions
        log_fw "GRANT PERMANENT: MAC=$mac has unlimited access"
    else
        # Temporary rule: create tracking file for cleanup script
        mkdir -p "$TRACKING_DIR"
        local session_file="$TRACKING_DIR/${mac//:/}.session"
        
        cat > "$session_file" <<EOF
mac=$mac
ip=$ip
expiry=$expiry
created=$(date +%s)
EOF
        
        log_fw "GRANT TEMPORARY: MAC=$mac IP=$ip expires at $(date -d "@$expiry" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo \"$expiry\")"
    fi
    
    return 0
}

# Revoke access: remove iptables rule and tracking file
revoke_access() {
    local mac="$1"
    local ip="$2"
    
    validate_mac "$mac" || return 1
    
    # Normalize MAC to uppercase
    mac=$(echo "$mac" | tr 'a-f' 'A-F')
    
    # Remove iptables rule
    iptables -D forwarding_rule -m mac --mac-source "$mac" -j ACCEPT 2>/dev/null || \
    iptables -D FORWARD -m mac --mac-source "$mac" -j ACCEPT 2>/dev/null || true
    log_fw "REVOKE: Removed iptables rule for MAC=$mac"
    
    # Remove from UCI firewall config (both permanent and temporary rules)
    if command -v uci >/dev/null 2>&1; then
        local fw_name="RemotWRT_permanent_${mac//:/}"
        if uci get firewall."$fw_name" >/dev/null 2>&1; then
            uci delete firewall."$fw_name"
            uci commit firewall
            log_fw "REVOKE: Removed UCI rule $fw_name"
        fi
        
        # Also try whitelist naming convention
        fw_name="RemotWRT_whitelist_${mac//:/}"
        if uci get firewall."$fw_name" >/dev/null 2>&1; then
            uci delete firewall."$fw_name"
            uci commit firewall
            log_fw "REVOKE: Removed UCI rule $fw_name"
        fi
    fi
    
    # Remove tracking file if exists
    local session_file="$TRACKING_DIR/${mac//:/}.session"
    if [ -f "$session_file" ]; then
        rm -f "$session_file"
        log_fw "REVOKE: Removed session tracking file"
    fi
    
    # Deauthenticate via OpenNDS if IP provided
    if [ -n "$ip" ] && command -v ndsctl >/dev/null 2>&1; then
        ndsctl deauth "$ip" 2>/dev/null || true
        log_fw "REVOKE: Sent deauth to OpenNDS for IP=$ip"
    fi
    
    return 0
}

# Main
if [ $# -lt 3 ]; then
    usage
fi

action="$1"
mac="$2"
ip="$3"

case "$action" in
    grant)
        if [ $# -lt 5 ]; then
            echo "ERROR: grant requires 4 arguments: MAC IP permanent expiry_epoch"
            usage
        fi
        permanent="$4"
        expiry="$5"
        grant_access "$mac" "$ip" "$permanent" "$expiry"
        ;;
    revoke)
        revoke_access "$mac" "$ip"
        ;;
    *)
        echo "ERROR: Unknown action: $action"
        usage
        ;;
esac

exit 0
