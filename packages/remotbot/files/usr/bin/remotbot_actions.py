#!/usr/bin/env python3
import sys
import subprocess
import re

def is_valid_mac(mac: str) -> bool:
    return bool(re.match(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$", mac))

def run_command(command: str):
    subprocess.run(command, shell=True, capture_output=True)

def main():
    if len(sys.argv) < 3:
        print("Usage: remotbot_actions.py <MAC> <approve|block>")
        sys.exit(1)
        
    mac = sys.argv[1].lower().strip()
    action = sys.argv[2].lower().strip()
    
    if not is_valid_mac(mac):
        print(f"Invalid MAC: {mac}")
        sys.exit(1)
        
    if action == "approve":
        # Add to whitelist (uci)
        run_command(f"uci add_list remotbot.main.mac_whitelist='{mac}'")
        run_command("uci commit remotbot")
        print(f"Approved and whitelisted: {mac}")
    elif action == "block":
        # Find IP for revoke if possible
        ip = "?"
        try:
            # Try to find IP from ARP
            with open("/proc/net/arp", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4 and parts[3].lower() == mac:
                        ip = parts[0]
                        break
        except Exception:
            pass

        # Revoke voucher session first (single source of truth)
        run_command(f"/usr/bin/remotwrt_firewall_helper.sh revoke '{mac}' '{ip}'")

        # Add to blocked_macs (uci)
        run_command(f"uci add_list remotbot.main.blocked_macs='{mac}'")
        run_command("uci commit remotbot")
        
        # Apply iptables DROP
        run_command(f"iptables -I FORWARD -m mac --mac-source {mac} -j DROP 2>/dev/null")
        
        # Add firewall rule
        name = "Block_" + mac.replace(":", "")
        run_command(
            f"uci batch << EOF\n"
            f"add firewall rule\n"
            f"set firewall.@rule[-1].name='{name}'\n"
            f"set firewall.@rule[-1].src='lan'\n"
            f"set firewall.@rule[-1].dest='wan'\n"
            f"set firewall.@rule[-1].src_mac='{mac}'\n"
            f"set firewall.@rule[-1].target='REJECT'\n"
            f"commit firewall\n"
            f"EOF"
        )
        print(f"Blocked: {mac}")

if __name__ == "__main__":
    main()
