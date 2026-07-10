#!/usr/bin/env python3
"""
FAS (Forwarding Authentication Service) Server untuk OpenNDS
HTTP server standalone yang menangani autentikasi captive portal

Config dibaca dari UCI remotbot.main (reuse konfigurasi yang sama dengan pi4Bot.py):
  - bot_token: Token Telegram bot
  - allowed_users: User ID yang boleh approve/block
  - mac_whitelist: MAC yang sudah trusted (auto-approve)
  - fas_port: Port FAS server (default 2080)
  - fas_pending_file: File JSON untuk status pending (default /tmp/opennds_pending.json)
  - fas_notify_ttl: Throttle notifikasi dalam detik (default 300)

File ini jalan sebagai service terpisah (procd) bersama pi4Bot.py
Komunikasi hanya lewat file JSON shared (tidak ada socket/DB tambahan)

OpenNDS FAS Level 0 specification:
https://opennds.org/docs/fas.html

Catatan keamanan:
  - fas_secure_enabled='0' (clear text) karena ini internal network
  - Bisa di-upgrade ke level 1 (hashed token) kalau dipakai di jaringan lebih terbuka
"""

import os
import sys
import html
import json
import time
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from datetime import datetime
import logging

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/fas_server.log')
    ]
)
logger = logging.getLogger(__name__)

# ==================== UCI CONFIG ====================

def uci_get(key: str, default: str = "") -> str:
    """Baca nilai dari UCI OpenWrt"""
    try:
        r = subprocess.run(["uci", "get", key], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception as e:
        logger.debug(f"UCI get {key} error: {e}")
    return default

def load_config() -> dict:
    """Load konfigurasi dari UCI remotbot.main"""
    allowed_str = uci_get("remotbot.main.allowed_users", "")
    allowed_users = []
    for uid in allowed_str.replace(",", " ").split():
        uid = uid.strip()
        if uid.lstrip("-").isdigit():
            allowed_users.append(int(uid))
    
    mac_str = uci_get("remotbot.main.mac_whitelist", "")
    mac_whitelist = [m.strip().lower() for m in mac_str.replace(",", " ").split() if m.strip()]
    
    return {
        "bot_token":         uci_get("remotbot.main.bot_token", ""),
        "allowed_users":     allowed_users,
        "mac_whitelist":     mac_whitelist,
        "fas_port":          int(uci_get("remotbot.main.fas_port", "2080")),
        "fas_pending_file":  uci_get("remotbot.main.fas_pending_file", "/tmp/opennds_pending.json"),
        "fas_notify_ttl":    int(uci_get("remotbot.main.fas_notify_ttl", "300")),
        "language":          uci_get("remotbot.main.language", "id"),
    }

# ==================== PENDING FILE MANAGEMENT ====================

def load_pending() -> dict:
    """
    Load status pending dari file JSON shared
    Format: {mac: {"status": "pending|approved|blocked", "ip": "...", "hostname": "...", "timestamp": ...}}
    """
    cfg = load_config()
    path = cfg["fas_pending_file"]
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error(f"Error loading pending file: {e}")
    return {}

def save_pending(data: dict) -> bool:
    """
    Simpan status pending ke file JSON dengan atomic write
    Pakai os.replace biar aman dibaca proses lain (pi4Bot.py)
    """
    cfg = load_config()
    path = cfg["fas_pending_file"]
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        logger.error(f"Error saving pending file: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False

def get_mac_from_ip(ip: str) -> str:
    """Lookup MAC address dari IP via ip neigh atau arp"""
    try:
        # Coba ip neigh dulu (lebih modern)
        r = subprocess.run(["ip", "neigh", "show", ip], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            # Format: 192.168.1.100 dev br-lan lladdr aa:bb:cc:dd:ee:ff REACHABLE
            parts = r.stdout.strip().split()
            for i, p in enumerate(parts):
                if p.lower() == "lladdr" and i+1 < len(parts):
                    return parts[i+1].lower()
            # Fallback: cari pattern MAC
            import re
            mac_pattern = r"[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}"
            match = re.search(mac_pattern, r.stdout)
            if match:
                return match.group().lower()
        
        # Fallback ke arp -n
        r = subprocess.run(["arp", "-n", ip], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            lines = r.stdout.strip().split("\n")
            for line in lines[1:] if len(lines) > 1 else lines:
                parts = line.split()
                for p in parts:
                    if ":" in p and len(p) == 17:
                        return p.lower()
    except Exception as e:
        logger.error(f"MAC lookup error for {ip}: {e}")
    return ""

# ==================== TELEGRAM NOTIFICATION ====================

_notify_lock = threading.Lock()
_last_notify = {}  # {mac: timestamp}

def send_telegram_notification(mac: str, ip: str, hostname: str) -> bool:
    """
    Kirim notifikasi Telegram untuk device baru
    Pakai throttle berdasarkan fas_notify_ttl supaya tidak spam
    """
    cfg = load_config()
    
    if not cfg.get("bot_token"):
        logger.error("Bot token tidak dikonfigurasi")
        return False
    
    if not cfg.get("allowed_users"):
        logger.error("Allowed users tidak dikonfigurasi")
        return False
    
    # Throttle check
    now = time.time()
    ttl = cfg["fas_notify_ttl"]
    
    with _notify_lock:
        last = _last_notify.get(mac, 0)
        if now - last < ttl:
            logger.info(f"Notification throttled for {mac} ({now - last:.0f}s since last)")
            return False
        _last_notify[mac] = now
    
    # Build message
    lang = cfg.get("language", "id")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if lang == "en":
        text = (
            f"⚠️ <b>New Device Detected!</b>\n\n"
            f"MAC: <code>{mac}</code>\n"
            f"IP: <code>{ip}</code>\n"
            f"Hostname: <code>{hostname}</code>\n"
            f"Time: <code>{now_str}</code>\n\n"
            f"Approve or block this device?"
        )
        btn_approve = "✅ Approve"
        btn_block = "🚫 Block"
    else:
        text = (
            f"⚠️ <b>Perangkat Baru Terdeteksi!</b>\n\n"
            f"MAC: <code>{mac}</code>\n"
            f"IP: <code>{ip}</code>\n"
            f"Hostname: <code>{hostname}</code>\n"
            f"Waktu: <code>{now_str}</code>\n\n"
            f"Setujui atau blokir perangkat ini?"
        )
        btn_approve = "✅ Setujui"
        btn_block = "🚫 Blokir"
    
    # Inline keyboard dengan callback untuk FAS
    keyboard = {
        "inline_keyboard": [
            [{"text": btn_approve, "callback_data": f"ndsok_{mac}"},
             {"text": btn_block, "callback_data": f"ndsno_{mac}"}]
        ]
    }
    
    url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
    payload = {
        "chat_id": cfg["allowed_users"][0],  # Kirim ke user pertama
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(keyboard)
    }
    
    try:
        import requests
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            logger.info(f"Telegram notification sent for {mac}")
            return True
        else:
            logger.error(f"Telegram API error: {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
    
    return False

# ==================== SPLASH PAGE HTML ====================

def get_splash_page(mac: str, ip: str, hostname: str, status: str, language: str) -> str:
    """
    Generate splash page HTML dengan dark theme
    Font: Space Mono, DM Sans
    Accent: neon green #00e5a0 / cyan #00c8e0
    Background: gelap
    Auto-refresh tiap 4 detik untuk cek status approval
    """
    mac = html.escape(mac)
    ip = html.escape(ip)
    hostname = html.escape(hostname)
    
    if language == "en":
        title = "Network Access"
        waiting_title = "Waiting for Approval..."
        waiting_desc = "Your device is pending admin approval. Please wait."
        approved_title = "Access Granted!"
        approved_desc = "You can now access the internet."
        blocked_title = "Access Denied"
        blocked_desc = "Your device has been blocked by the administrator."
        refresh_hint = "This page will refresh automatically..."
    else:
        title = "Akses Jaringan"
        waiting_title = "Menunggu Persetujuan..."
        waiting_desc = "Perangkat Anda menunggu persetujuan admin. Mohon tunggu."
        approved_title = "Akses Diberikan!"
        approved_desc = "Anda sekarang dapat mengakses internet."
        blocked_title = "Akses Ditolak"
        blocked_desc = "Perangkat Anda telah diblokir oleh administrator."
        refresh_hint = "Halaman ini akan refresh otomatis..."
    
    # Status-based content
    if status == "approved":
        status_color = "#00e5a0"  # neon green
        status_icon = "✅"
        content_title = approved_title
        content_desc = approved_desc
        extra_meta = '<meta http-equiv="refresh" content="5;url=http://captiveportal.net/success">'
    elif status == "blocked":
        status_color = "#ff4444"  # red
        status_icon = "🚫"
        content_title = blocked_title
        content_desc = blocked_desc
        extra_meta = ''
    else:  # pending
        status_color = "#00c8e0"  # cyan
        status_icon = "⏳"
        content_title = waiting_title
        content_desc = waiting_desc
        extra_meta = '<meta http-equiv="refresh" content="4">'
    
    html = f'''<!DOCTYPE html>
<html lang="{language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {extra_meta}
    <title>{title}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;700&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'DM Sans', sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #ffffff;
            padding: 20px;
        }}
        
        .container {{
            max-width: 480px;
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .logo {{
            font-size: 48px;
            margin-bottom: 15px;
        }}
        
        h1 {{
            font-family: 'Space Mono', monospace;
            font-size: 24px;
            font-weight: 700;
            color: {status_color};
            margin-bottom: 10px;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            background: rgba({int(status_color[1:3], 16)}, {int(status_color[3:5], 16)}, {int(status_color[5:7], 16)}, 0.2);
            border: 1px solid {status_color};
            border-radius: 20px;
            font-family: 'Space Mono', monospace;
            font-size: 14px;
            color: {status_color};
            margin-bottom: 20px;
        }}
        
        .content {{
            text-align: center;
        }}
        
        .icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}
        
        h2 {{
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 15px;
        }}
        
        p {{
            font-size: 14px;
            line-height: 1.6;
            color: rgba(255, 255, 255, 0.7);
            margin-bottom: 20px;
        }}
        
        .device-info {{
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            padding: 15px;
            margin-top: 25px;
            text-align: left;
        }}
        
        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            font-size: 13px;
            font-family: 'Space Mono', monospace;
        }}
        
        .info-row:last-child {{
            border-bottom: none;
        }}
        
        .info-label {{
            color: rgba(255, 255, 255, 0.5);
        }}
        
        .info-value {{
            color: {status_color};
        }}
        
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top-color: {status_color};
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .refresh-hint {{
            text-align: center;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.4);
            margin-top: 20px;
            font-family: 'Space Mono', monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🌐</div>
            <h1>{title}</h1>
            <div class="status-badge">{status_icon} {status.upper()}</div>
        </div>
        
        <div class="content">
            <div class="icon">{status_icon}</div>
            <h2>{content_title}</h2>
            <p>{content_desc}</p>
            
            {'<div class="spinner"></div>' if status == 'pending' else ''}
            
            <div class="device-info">
                <div class="info-row">
                    <span class="info-label">MAC Address</span>
                    <span class="info-value">{mac}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">IP Address</span>
                    <span class="info-value">{ip}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Hostname</span>
                    <span class="info-value">{hostname}</span>
                </div>
            </div>
            
            <div class="refresh-hint">{refresh_hint}</div>
        </div>
    </div>
</body>
</html>'''
    
    return html

# ==================== HTTP REQUEST HANDLER ====================

class FASHandler(BaseHTTPRequestHandler):
    """HTTP handler untuk FAS OpenNDS"""
    
    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")
    
    def do_GET(self):
        """Handle GET requests dari OpenNDS FAS"""
        parsed = urlparse(self.path)
        
        if parsed.path == "/fas":
            self.handle_fas(parsed.query)
        elif parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/fas")
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")
    
    def handle_fas(self, query_string: str):
        """
        Handle FAS request dari OpenNDS
        
        Query parameters (FAS Level 0):
          - clientip: IP address client
          - gatewayname: Nama gateway
          - tok: Token (empty untuk level 0)
          - redir: URL redirect setelah auth
          - authaction: URL untuk submit authentication
        
        Flow:
          1. Lookup MAC dari clientip
          2. Cek apakah MAC ada di whitelist → auto-approve
          3. Cek status di pending file → approved/blocked/pending
          4. Jika baru → simpan pending + kirim notifikasi Telegram
          5. Tampilkan splash page sesuai status
        """
        cfg = load_config()
        params = parse_qs(query_string)
        
        # Extract FAS parameters
        client_ip = params.get("clientip", [""])[0]
        gateway_name = params.get("gatewayname", ["Unknown"])[0]
        tok = params.get("tok", [""])[0]
        redir = params.get("redir", [""])[0]
        authaction = params.get("authaction", [""])[0]
        
        logger.info(f"FAS request: ip={client_ip}, gateway={gateway_name}")
        
        if not client_ip:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Missing clientip parameter")
            return
        
        # Lookup MAC address
        mac = get_mac_from_ip(client_ip)
        if not mac:
            logger.warning(f"Cannot find MAC for IP {client_ip}")
            mac = "unknown"
        
        # Get hostname (optional)
        hostname = "unknown"
        try:
            r = subprocess.run(["nslookup", client_ip], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                lines = r.stdout.strip().split("\n")
                for line in reversed(lines):
                    if "name =" in line:
                        hostname = line.split("name =")[-1].strip().rstrip(".")
                        break
        except Exception:
            pass
        
        # Load pending status
        pending = load_pending()
        status_data = pending.get(mac, {})
        current_status = status_data.get("status", "pending")
        
        # Check whitelist first
        mac_lower = mac.lower()
        if mac_lower in cfg["mac_whitelist"]:
            logger.info(f"MAC {mac} in whitelist - auto-approve")
            current_status = "approved"
        
        # Handle new device
        if mac not in pending and mac_lower not in cfg["mac_whitelist"]:
            logger.info(f"New device detected: {mac} ({client_ip})")
            # Save as pending
            pending[mac] = {
                "status": "pending",
                "ip": client_ip,
                "hostname": hostname,
                "timestamp": time.time(),
                "gateway": gateway_name
            }
            save_pending(pending)
            # Send Telegram notification
            send_telegram_notification(mac, client_ip, hostname)
            current_status = "pending"
        
        # Handle approved status - redirect to authaction
        if current_status == "approved":
            logger.info(f"MAC {mac} approved - redirecting")
            # Remove from pending after approval
            if mac in pending:
                del pending[mac]
                save_pending(pending)
            
            # Redirect ke authaction URL dari OpenNDS
            if authaction:
                self.send_response(302)
                self.send_header("Location", authaction)
                self.end_headers()
                return
        
        # Handle blocked status
        if current_status == "blocked":
            logger.info(f"MAC {mac} blocked - showing denied page")
        
        # Show splash page
        html = get_splash_page(mac, client_ip, hostname, current_status, cfg.get("language", "id"))
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

# ==================== MAIN ====================

def main():
    """Start FAS server"""
    cfg = load_config()
    
    # Validate config
    if not cfg.get("bot_token"):
        logger.error("ERROR: Bot token belum dikonfigurasi!")
        logger.error("Run: uci set remotbot.main.bot_token='TOKEN'")
        sys.exit(1)
    
    if not cfg.get("allowed_users"):
        logger.error("ERROR: Allowed users belum dikonfigurasi!")
        logger.error("Run: uci set remotbot.main.allowed_users='USER_ID'")
        sys.exit(1)
    
    port = cfg["fas_port"]
    
    # Initialize pending file
    if not os.path.exists(cfg["fas_pending_file"]):
        save_pending({})
        logger.info(f"Initialized pending file: {cfg['fas_pending_file']}")
    
    # Start server
    server = HTTPServer(("0.0.0.0", port), FASHandler)
    logger.info(f"FAS Server started on port {port}")
    logger.info(f"Pending file: {cfg['fas_pending_file']}")
    logger.info(f"Notify TTL: {cfg['fas_notify_ttl']}s")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down FAS Server...")
        server.shutdown()

if __name__ == "__main__":
    main()
