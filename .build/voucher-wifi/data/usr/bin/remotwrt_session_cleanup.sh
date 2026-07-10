#!/bin/sh
# remotwrt_session_cleanup.sh - Cleanup expired non-permanent sessions
# Runs every minute via cron to check and revoke expired sessions
# Location: /usr/bin/remotwrt_session_cleanup.sh

LOG_FILE="/var/log/voucher_login.log"
TRACKING_DIR="/tmp/remotwrt_sessions"

# Create tracking directory if not exists
mkdir -p "$TRACKING_DIR"

log_cleanup() {
    logger -t "remotwrt_cleanup" "$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - CLEANUP - $1" >> "$LOG_FILE"
}

# Get current time in epoch
current_time=$(date +%s)

# Process each session file
for session_file in "$TRACKING_DIR"/*.session 2>/dev/null; do
    [ -f "$session_file" ] || continue
    
    # Read session data
    mac=""
    ip=""
    expiry=""
    
    while IFS='=' read -r key value; do
        case "$key" in
            mac) mac="$value" ;;
            ip) ip="$value" ;;
            expiry) expiry="$value" ;;
        esac
    done < "$session_file"
    
    # Skip if missing required fields
    if [ -z "$mac" ] || [ -z "$ip" ] || [ -z "$expiry" ]; then
        continue
    fi
    
    # Check if expired
    if [ "$current_time" -gt "$expiry" ]; then
        log_cleanup "EXPIRED - Session diputus: MAC=$mac IP=$ip"
        
        # Remove iptables rule for this MAC
        iptables -D forwarding_rule -m mac --mac-source "$mac" -j ACCEPT 2>/dev/null || true
        iptables -D FORWARD -m mac --mac-source "$mac" -j ACCEPT 2>/dev/null || true
        
        # Deauthenticate via OpenNDS (ndsctl deauth)
        # Note: ndsctl deauth expects IP address
        if command -v ndsctl >/dev/null 2>&1; then
            ndsctl deauth "$ip" 2>/dev/null || true
        fi
        
        # Remove from firewall config (UCI)
        if command -v uci >/dev/null 2>&1; then
            uci delete firewall."RemotWRT_whitelist_${mac//:/}" 2>/dev/null && uci commit firewall 2>/dev/null || true
        fi
        
        # Remove session file
        rm -f "$session_file"
        
        log_cleanup "Session removed: MAC=$mac"
    fi
done

# Also cleanup orphaned session files (no matching device in ARP table)
# This prevents accumulation of stale entries
for session_file in "$TRACKING_DIR"/*.session 2>/dev/null; do
    [ -f "$session_file" ] || continue
    
    mac=$(grep "^mac=" "$session_file" 2>/dev/null | cut -d'=' -f2)
    if [ -n "$mac" ]; then
        # Check if MAC exists in ARP table
        if ! grep -qi "$mac" /proc/net/arp 2>/dev/null; then
            # Device no longer connected, remove session
            rm -f "$session_file"
            log_cleanup "Orphaned session removed: MAC=$mac (device disconnected)"
        fi
    fi
done

exit 0
