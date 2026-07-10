#!/bin/sh
# RemotWRT Monitor Script - Real-time device tracking and statistics

LOG_FILE="/var/log/remotwrt.log"
HISTORY_FILE="/var/lib/remotwrt/device_history.json"
STATE_FILE="/var/run/remotwrt.state"

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

get_connected_devices() {
    # Get devices from OpenNDS
    if command -v ndsctl >/dev/null 2>&1; then
        ndsctl clients 2>/dev/null | grep -E "^[0-9]" || true
    fi
    
    # Get devices from ARP table
    cat /proc/net/arp 2>/dev/null | grep -v "^IP" | grep -v "00:00:00:00:00:00" || true
    
    # Get wireless associations
    for iface in $(iwinfo 2>/dev/null | grep -oE "wlan[0-9]+" | sort -u); do
        iwinfo $iface assoclist 2>/dev/null || true
    done
}

check_new_device() {
    local mac="$1"
    local ip="$2"
    
    # Check if device is in whitelist
    if uci get remotwrt.@firewall_whitelist[*].mac 2>/dev/null | grep -q "$mac"; then
        return 0  # Whitelisted, allow access
    fi
    
    # Check if device is in blacklist
    if uci get remotwrt.@firewall_blacklist[*].mac 2>/dev/null | grep -q "$mac"; then
        return 1  # Blacklisted, block access
    fi
    
    # Check if device is authenticated via OpenNDS
    if ndsctl status 2>/dev/null | grep -q "$mac"; then
        return 0  # Authenticated
    fi
    
    return 2  # New device, needs authentication
}

update_device_history() {
    local mac="$1"
    local ip="$2"
    local timestamp=$(date +%s)
    
    # Append to history file (simple JSON format)
    echo "{\"mac\":\"$mac\",\"ip\":\"$ip\",\"timestamp\":$timestamp,\"event\":\"connect\"}" >> "$HISTORY_FILE"
}

generate_voucher() {
    local category="$1"
    local validity="$2"
    local code=$(echo "$category$(date +%s)" | md5sum | cut -c1-8 | tr 'a-f' 'A-F')
    
    echo "$code"
}

bind_voucher_to_mac() {
    local code="$1"
    local mac="$2"
    local ip="$3"
    
    # Add to UCI config
    local section_id=$(uci add remotwrt voucher_binding)
    uci set remotwrt.$section_id.code="$code"
    uci set remotwrt.$section_id.mac="$mac"
    uci set remotwrt.$section_id.ip="$ip"
    uci set remotwrt.$section_id.status="active"
    uci commit remotwrt
}

# Main monitoring loop
main_loop() {
    log_msg "RemotWRT Monitor started"
    
    while true; do
        # Get current devices
        devices=$(get_connected_devices)
        
        # Process each device
        echo "$devices" | while read -r line; do
            if [ -n "$line" ]; then
                mac=$(echo "$line" | awk '{print $2}')
                ip=$(echo "$line" | awk '{print $1}')
                
                if [ -n "$mac" ] && [ -n "$ip" ]; then
                    check_new_device "$mac" "$ip"
                    case $? in
                        0)
                            # Known device
                            ;;
                        1)
                            # Blacklisted device
                            log_msg "Blocked device: $mac ($ip)"
                            ;;
                        2)
                            # New device
                            log_msg "New device detected: $mac ($ip)"
                            update_device_history "$mac" "$ip"
                            ;;
                    esac
                fi
            fi
        done
        
        # Save state
        echo "$devices" > "$STATE_FILE"
        
        sleep 30
    done
}

case "$1" in
    start)
        main_loop &
        ;;
    stop)
        killall remotwrt_monitor.sh
        ;;
    status)
        if [ -f "$STATE_FILE" ]; then
            echo "RemotWRT Monitor is running"
            cat "$STATE_FILE"
        else
            echo "RemotWRT Monitor is not running"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
