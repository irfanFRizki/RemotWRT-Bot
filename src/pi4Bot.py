#!/usr/bin/env python3
"""
OpenWRT Telegram Monitoring Bot untuk Raspberry Pi 4
Features:
  - Monitoring CPU, RAM, Disk, Traffic, IP, Ping, Speedtest
  - Notifikasi otomatis (CPU panas, RAM penuh)
  - Alert WAN disconnect jika putus > batas waktu (default 60 menit)
  - Blokir device tidak terdaftar (by MAC whitelist)
  - Multi-bahasa ID/EN toggle
  - Service control (start/stop/restart)
"""

import asyncio
import logging
import subprocess
import json
import os
import time
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==================== CONFIG ====================
CONFIG_FILE = "/etc/remotbot/config.json"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    default = {
        "bot_token": "",
        "allowed_users": [],
        "cgi_online_path": "/www/cgi-bin/online",
        "language": "id",
        "cpu_temp_threshold": 75,
        "ram_threshold": 85,
        "wan_timeout_minutes": 60,
        "mac_whitelist": [],
        "notify_cpu_temp": True,
        "notify_ram": True,
        "notify_wan": True,
        "notify_unknown_device": True,
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return {**default, **json.load(f)}
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
    return default

def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False

# ==================== I18N ====================
STRINGS = {
    "id": {
        "unauthorized":      "❌ Akses tidak diizinkan!",
        "welcome":           "🤖 <b>OpenWRT Monitoring Bot</b>\n\nSelamat datang! Pilih menu di bawah:",
        "nav_hint":          "Gunakan tombol di bawah untuk navigasi cepat:",
        "menu":              "📋 <b>MENU UTAMA</b>\n\nPilih menu yang Anda inginkan:",
        "refreshed":         "🔄 <b>Refreshed!</b>\n\nData terbaru tersedia.",
        "cmd_format":        "❌ Format: <code>/cmd perintah_anda</code>",
        "cmd_blocked":       "❌ Perintah berbahaya diblokir!",
        "executing":         "⏳ Menjalankan...",
        "loading":           "⏳ Memuat...",
        "processing":        "⏳ Memproses...",
        "error":             "❌ Terjadi kesalahan",
        "back_menu":         "🔙 Kembali ke Menu",
        "service_ctrl":      "🔧 Kontrol Service",
        "lang_changed":      "✅ Bahasa diubah ke Bahasa Indonesia",
        "settings_saved":    "✅ Pengaturan disimpan",
        "wan_down_alert":    "🚨 <b>ALERT: Koneksi WAN Terputus!</b>\n\nWaktu: <code>{time}</code>",
        "wan_up_alert":      "✅ <b>Koneksi WAN Pulih!</b>\n\nDowntime: <code>{duration}</code>\nWaktu: <code>{time}</code>",
        "wan_long_down":     "⚠️ <b>WAN masih terputus selama {duration}!</b>\n\nSegera periksa koneksi internet.",
        "cpu_temp_alert":    "🌡 <b>ALERT: Suhu CPU Tinggi!</b>\n\nSuhu: <code>{temp}°C</code> (batas: {threshold}°C)\nWaktu: <code>{time}</code>",
        "ram_alert":         "💾 <b>ALERT: RAM Hampir Penuh!</b>\n\nPenggunaan: <code>{usage}%</code> (batas: {threshold}%)\nWaktu: <code>{time}</code>",
        "unknown_device":    "⚠️ <b>Perangkat Tidak Dikenal!</b>\n\nMAC: <code>{mac}</code>\nIP: <code>{ip}</code>\nHostname: <code>{hostname}</code>\nWaktu: <code>{time}</code>\n\nIngin memblokir perangkat ini?",
        "device_blocked":    "🚫 <b>Perangkat Diblokir</b>\n\nMAC: <code>{mac}</code>\nIP: <code>{ip}</code>",
        "device_unblocked":  "✅ <b>Perangkat Diizinkan</b>\n\nMAC: <code>{mac}</code>",
        "whitelist_empty":   "📋 Whitelist MAC kosong.\nSemua perangkat diizinkan.",
        "block_title":       "🚫 <b>Manajemen Blokir Device</b>",
        "no_blocked":        "Tidak ada perangkat yang diblokir.",
        "settings_title":    "⚙️ <b>Pengaturan Bot</b>",
        "lang_label":        "Bahasa",
    },
    "en": {
        "unauthorized":      "❌ Unauthorized access!",
        "welcome":           "🤖 <b>OpenWRT Monitoring Bot</b>\n\nWelcome! Choose menu below:",
        "nav_hint":          "Use buttons below for quick navigation:",
        "menu":              "📋 <b>MAIN MENU</b>\n\nChoose an option:",
        "refreshed":         "🔄 <b>Refreshed!</b>\n\nLatest data available.",
        "cmd_format":        "❌ Format: <code>/cmd your_command</code>",
        "cmd_blocked":       "❌ Dangerous command blocked!",
        "executing":         "⏳ Executing...",
        "loading":           "⏳ Loading...",
        "processing":        "⏳ Processing...",
        "error":             "❌ An error occurred",
        "back_menu":         "🔙 Back to Menu",
        "service_ctrl":      "🔧 Service Control",
        "lang_changed":      "✅ Language changed to English",
        "settings_saved":    "✅ Settings saved",
        "wan_down_alert":    "🚨 <b>ALERT: WAN Connection Down!</b>\n\nTime: <code>{time}</code>",
        "wan_up_alert":      "✅ <b>WAN Connection Restored!</b>\n\nDowntime: <code>{duration}</code>\nTime: <code>{time}</code>",
        "wan_long_down":     "⚠️ <b>WAN still down for {duration}!</b>\n\nPlease check your internet connection.",
        "cpu_temp_alert":    "🌡 <b>ALERT: CPU Temperature High!</b>\n\nTemp: <code>{temp}°C</code> (limit: {threshold}°C)\nTime: <code>{time}</code>",
        "ram_alert":         "💾 <b>ALERT: RAM Almost Full!</b>\n\nUsage: <code>{usage}%</code> (limit: {threshold}%)\nTime: <code>{time}</code>",
        "unknown_device":    "⚠️ <b>Unknown Device Detected!</b>\n\nMAC: <code>{mac}</code>\nIP: <code>{ip}</code>\nHostname: <code>{hostname}</code>\nTime: <code>{time}</code>\n\nDo you want to block this device?",
        "device_blocked":    "🚫 <b>Device Blocked</b>\n\nMAC: <code>{mac}</code>\nIP: <code>{ip}</code>",
        "device_unblocked":  "✅ <b>Device Allowed</b>\n\nMAC: <code>{mac}</code>",
        "whitelist_empty":   "📋 MAC whitelist is empty.\nAll devices are allowed.",
        "block_title":       "🚫 <b>Device Block Management</b>",
        "no_blocked":        "No blocked devices.",
        "settings_title":    "⚙️ <b>Bot Settings</b>",
        "lang_label":        "Language",
    }
}

def t(key, cfg=None, **kwargs):
    if cfg is None: cfg = load_config()
    lang = cfg.get("language","id")
    s = STRINGS.get(lang, STRINGS["id"]).get(key, STRINGS["id"].get(key, key))
    if kwargs:
        try: s = s.format(**kwargs)
        except: pass
    return s

# ==================== MONITOR STATE ====================
monitor_state = {
    "wan_down_since": None,
    "wan_alert_sent": False,
    "wan_long_alert_sent": False,
    "last_cpu_alert": 0,
    "last_ram_alert": 0,
    "alerted_macs": set(),
}

# ==================== UTILS ====================
def check_auth(user_id):
    return user_id in load_config().get("allowed_users", [])

def run_command(command, timeout=30):
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else f"Error: {r.stderr.strip()}"
    except subprocess.TimeoutExpired: return "Error: Command timeout"
    except Exception as e: return f"Error: {str(e)}"

def format_bytes(b):
    if b < 1024: return f"{b} B"
    elif b < 1024**2: return f"{b/1024:.2f} KB"
    elif b < 1024**3: return f"{b/1024**2:.2f} MB"
    return f"{b/1024**3:.2f} GB"

def format_duration(secs):
    secs = int(secs)
    if secs < 60: return f"{secs}s"
    elif secs < 3600: return f"{secs//60}m {secs%60}s"
    return f"{secs//3600}j {(secs%3600)//60}m"

# ==================== SYSTEM INFO ====================
def get_cpu_temp():
    try:
        raw = run_command("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
        if raw and raw.replace('-','').isdigit(): return float(raw)/1000
    except: pass
    return 0.0

def get_ram_usage():
    try:
        mem = run_command("free | grep Mem").split()
        if len(mem) >= 3: return int(int(mem[2])/int(mem[1])*100)
    except: pass
    return 0

def check_wan():
    for host in ["8.8.8.8","1.1.1.1","114.114.114.114"]:
        r = run_command(f"ping -c 1 -W 3 {host}", timeout=10)
        if "1 received" in r: return True
    return False

def get_current_devices():
    try:
        cfg = load_config()
        r = subprocess.run(["bash", cfg.get("cgi_online_path","/www/cgi-bin/online")],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            lines = r.stdout.strip().split('\n')
            js = next((i for i,l in enumerate(lines) if l.strip().startswith('[')), -1)
            if js != -1: return json.loads('\n'.join(lines[js:]))
    except: pass
    return []

def block_mac(mac):
    mac = mac.lower().strip()
    run_command(f"iptables -I FORWARD -m mac --mac-source {mac} -j DROP")
    run_command(f"uci add firewall rule; uci set firewall.@rule[-1].name='Block_{mac.replace(':','')}'; "
                f"uci set firewall.@rule[-1].src='lan'; uci set firewall.@rule[-1].dest='wan'; "
                f"uci set firewall.@rule[-1].src_mac='{mac}'; uci set firewall.@rule[-1].target='REJECT'; "
                f"uci commit firewall")
    return True

def unblock_mac(mac):
    mac = mac.lower().strip()
    run_command(f"iptables -D FORWARD -m mac --mac-source {mac} -j DROP 2>/dev/null")
    name = mac.replace(':','')
    run_command(f"for i in $(uci show firewall | grep 'Block_{name}' | cut -d. -f1-2 | head -1); do uci delete $i; done; uci commit firewall 2>/dev/null")
    return True

def get_blocked_macs():
    r = run_command("iptables -L FORWARD -n | grep MAC | awk '{print $NF}' | sed 's/MAC=//'")
    if r and "Error" not in r: return [m.strip().lower() for m in r.split('\n') if m.strip()]
    return []

# ==================== BOT FEATURES ====================
def get_cpu_ram_info():
    try:
        if run_command("which sysinfo.sh"):
            result = run_command("sysinfo.sh --plain")
            lines = result.split('\n'); out = []; capture = False
            for line in lines:
                if '=== System Info ===' in line: capture = True
                if capture and 'RAM Available:' in line: out.append(line); break
                if any(x in line for x in ['=== Disk','=== Network','=== System Time']): break
                if capture: out.append(line)
            r = "🖥 <b>CPU & RAM Status</b>\n\n" + '\n'.join(out)
            for h in ["System Info","CPU Temperature","CPU Usage","Load Average","CPU Info","Memory (RAM)","Swap"]:
                r = r.replace(f"=== {h} ===", f"<b>=== {h} ===</b>")
            return r
        temp = get_cpu_temp()
        load = run_command("cat /proc/loadavg").split()[:3]
        cpu = run_command("top -bn1 | grep 'CPU:' | awk '{print $2}'") or "N/A"
        mem = run_command("free | grep Mem").split()
        if len(mem)>=4:
            total,used,free = int(mem[1]),int(mem[2]),int(mem[3])
            pct = int(used/total*100) if total else 0
            return (f"🖥 <b>CPU & RAM Status</b>\n\n🌡 Suhu: <code>{temp:.0f}°C</code>\n"
                    f"📊 CPU: <code>{cpu}%</code>\n⚡ Load: <code>{' '.join(load)}</code>\n"
                    f"💾 RAM: <code>{pct}% ({used//1024}MB / {total//1024}MB)</code>\n"
                    f"💾 Bebas: <code>{free//1024}MB</code>")
    except Exception as e: return f"Error: {str(e)}"
    return "Error: Unable to get info"

def get_online_users():
    try:
        devices = get_current_devices()
        if not devices: return "👥 <b>Online Users</b>\n\nTidak ada perangkat online"
        em = {"TERHUBUNG":"🟢","TERHUBUNG TIDAK AKTIF":"🟡","TIDAK DIKETAHUI":"🟠","TIDAK TERHUBUNG":"🔴"}
        text = "👥 <b>Online Users</b>\n\n"
        for i,d in enumerate(devices,1):
            hn = d.get('hostname','*') if d.get('hostname','*') != '*' else 'Unknown'
            text += f"{i}. {em.get(d.get('status',''),'⚪')} <b>{hn}</b>\n   IP: <code>{d.get('ip','')}</code>\n   MAC: <code>{d.get('mac','')}</code>\n   Status: {d.get('status','')}\n\n"
        return text
    except Exception as e: return f"Error: {str(e)}"

def get_vnstat_traffic():
    try:
        text = "📊 <b>Traffic (eth1)</b>\n\n"
        try:
            r = subprocess.run(["sh","/www/cgi-bin/traffic"],capture_output=True,text=True,timeout=10)
            if r.returncode==0:
                lines=r.stdout.strip().split('\n')
                js=next((i for i,l in enumerate(lines) if l.strip().startswith('{')), -1)
                if js!=-1:
                    d=json.loads('\n'.join(lines[js:]))
                    if "error" not in d:
                        text+=f"📡 <b>Live:</b>\n⬇️ {format_bytes(int(d.get('rx',0)))}\n⬆️ {format_bytes(int(d.get('tx',0)))}\n\n"
        except: pass
        for p,flag,label in [('d','day','📅 Hari ini'),('m','month','📈 Bulan ini')]:
            try:
                data=json.loads(run_command(f"vnstat --json {p} -i eth1"))
                if data and 'interfaces' in data:
                    items=data['interfaces'][0]['traffic'][flag]
                    if items:
                        last=items[-1]; rx,tx=last['rx'],last['tx']
                        text+=f"<b>{label}:</b>\n⬇️ {format_bytes(rx)}\n⬆️ {format_bytes(tx)}\n📊 Total: {format_bytes(rx+tx)}\n\n"
            except: pass
        return text.strip()
    except Exception as e: return f"Error: {str(e)}"

def get_my_ip():
    try:
        for svc in ["https://api.ipify.org","https://ifconfig.me","https://icanhazip.com"]:
            try:
                r=requests.get(svc,timeout=5)
                if r.status_code==200:
                    ip=r.text.strip()
                    try:
                        info=requests.get(f"https://ipinfo.io/{ip}/json",timeout=5).json()
                        return (f"🌍 <b>Public IP</b>\n\nIP: <code>{ip}</code>\nISP: <code>{info.get('org','N/A')}</code>\n"
                                f"Lokasi: <code>{info.get('city','N/A')}, {info.get('region','N/A')}</code>")
                    except: return f"🌍 <b>Public IP:</b> <code>{ip}</code>"
            except: continue
        return "Error: Tidak bisa mendapat IP publik"
    except Exception as e: return f"Error: {str(e)}"

def ping_test(host="8.8.8.8"):
    r = run_command(f"ping -c 4 {host}")
    stats = [l for l in r.split('\n') if 'min/avg/max' in l or 'packet loss' in l]
    return f"🔍 <b>Ping ({host})</b>\n\n<code>{chr(10).join(stats)}</code>"

def speedtest():
    for binary in ["/usr/bin/speedtest-ookla","/usr/bin/speedtest"]:
        if run_command(f"test -f {binary} && echo OK") == "OK":
            r = run_command(f"timeout 60 {binary} --accept-license --accept-gdpr 2>&1")
            if "timeout" in r.lower(): return "⚡ Speedtest timeout >60 detik"
            lines=r.split('\n'); server=ping=dl=ul=""
            for line in lines:
                if "Server:" in line: server=line.split("Server:")[1].strip()
                elif "Latency:" in line or "Idle Latency:" in line:
                    p=line.split(":"); ping=p[-1].strip().split()[0] if len(p)>1 and p[-1].strip() else ""
                elif "Download:" in line: dl=line.split("Download:")[1].strip()
                elif "Upload:" in line: ul=line.split("Upload:")[1].strip()
            txt=f"⚡ <b>Speedtest Results</b>\n\n"
            if server: txt+=f"🌐 <code>{server}</code>\n"
            if ping: txt+=f"📶 Latency: <code>{ping} ms</code>\n"
            if dl: txt+=f"⬇️ Download: <code>{dl}</code>\n"
            if ul: txt+=f"⬆️ Upload: <code>{ul}</code>\n"
            return txt or f"<code>{r[:500]}</code>"
    if run_command("which speedtest-cli"):
        r=run_command("timeout 60 speedtest-cli --simple 2>&1")
        p=d=u=""
        for line in r.split('\n'):
            if "Ping:" in line: p=line.split("Ping:")[1].strip()
            elif "Download:" in line: d=line.split("Download:")[1].strip()
            elif "Upload:" in line: u=line.split("Upload:")[1].strip()
        return f"⚡ <b>Speedtest</b>\n\n📶 {p or 'N/A'}\n⬇️ {d or 'N/A'}\n⬆️ {u or 'N/A'}"
    return "⚠️ Speedtest tidak terinstall.\nInstall: <code>pip3 install speedtest-cli</code>"

def get_disk_info():
    result="💿 <b>Disk Usage</b>\n\n"; found=False
    for disk in ["sda1","sdb1","root","mmcblk0p3"]:
        info=run_command(f"df -h | grep {disk}")
        if info:
            p=info.split()
            if len(p)>=5: result+=f"<b>{disk}:</b> Size:<code>{p[1]}</code> Used:<code>{p[2]}</code> Free:<code>{p[3]}</code> <code>{p[4]}</code>\n\n"; found=True
    return result.strip() if found else result+"Tidak ada disk"

def check_services():
    result="⚙️ <b>Services Status</b>\n\n"
    for svc in ["openclash","nikki","cloudflared"]:
        st=run_command(f"service {svc} status 2>&1").lower()
        if "running" in st or "active" in st: result+=f"✅ <b>{svc}:</b> RUNNING\n"
        elif "inactive" in st or "stopped" in st: result+=f"❌ <b>{svc}:</b> STOPPED\n"
        elif "not found" in st or "usage" in st: result+=f"❓ <b>{svc}:</b> NOT INSTALLED\n"
        else:
            ps=run_command(f"ps | grep {svc} | grep -v grep")
            result+=f"{'✅' if ps else '❌'} <b>{svc}:</b> {'RUNNING' if ps else 'STOPPED'}\n"
    return result

def service_control(name, action):
    if action not in ["start","stop","restart"]: return "❌ Action tidak valid"
    r=run_command(f"service {name} {action} 2>&1")
    time.sleep(2)
    st=run_command(f"service {name} status 2>&1")
    return f"⚙️ <b>{name}</b> → <code>{action}</code>\n\n<b>Result:</b>\n<code>{r}</code>\n\n<b>Status:</b>\n<code>{st}</code>"

def get_container_info():
    result="🐳 <b>Containers</b>\n\n"
    tool="docker" if run_command("which docker") else "podman" if run_command("which podman") else None
    if not tool: return result+"❌ Docker/Podman tidak terinstall"
    containers=run_command(f"{tool} ps -a --format '{{{{.Names}}}}|{{{{.Status}}}}|{{{{.Image}}}}'")
    if containers and "Error" not in containers:
        for line in containers.split('\n'):
            if line:
                p=line.split('|')
                if len(p)>=3: result+=f"{'🟢' if 'Up' in p[1] else '🔴'} <b>{p[0]}</b>\n   <code>{p[2]}</code> — <code>{p[1]}</code>\n\n"
    else: result+="Tidak ada container"
    return result

def leak_test():
    try:
        text="🔒 <b>Leak Test</b>\n\n"
        try: ip=requests.get("https://api.ipify.org",timeout=5).text.strip(); text+=f"🌍 IP: <code>{ip}</code>\n\n"
        except: ip="unknown"; text+="🌍 IP: N/A\n\n"
        text+="🔍 <b>DNS Check:</b>\n"
        for domain,name in [("whoami.akamai.net","Akamai"),("myip.opendns.com","OpenDNS")]:
            dr=run_command(f"nslookup {domain} 2>&1"); rip=None
            for line in dr.split('\n'):
                if 'Address' in line and '127.0.0.1' not in line and '#53' not in line:
                    p=line.split()
                    if len(p)>=2: rip=p[-1]; break
            text+=f"• {name}: <code>{rip or 'N/A'}</code>\n"
        try:
            info=requests.get(f"http://ip-api.com/json/{ip}",timeout=5).json()
            if info.get("status")=="success":
                text+=f"\n{'✅ VPN/Proxy detected' if info.get('proxy') or info.get('hosting') else '⚠️ Direct connection'}\n"
                text+=f"📍 <code>{info.get('city','N/A')}, {info.get('country','N/A')}</code>\n"
        except: pass
        return text
    except Exception as e: return f"Error: {str(e)}"

def adblock_test():
    domains=[("ads.google.com","Google Ads"),("doubleclick.net","DoubleClick"),
             ("googleadservices.com","Google Ad Services"),("adservice.google.com","Ad Service")]
    result="🛡 <b>AdBlock Test</b>\n\n"; blocked=0
    for domain,name in domains:
        chk=run_command(f"nslookup {domain} 2>&1")
        ok="NXDOMAIN" in chk or "0.0.0.0" in chk or "127.0.0.1" in chk or "can't resolve" in chk.lower()
        result+=f"{'✅' if ok else '❌'} {name}\n"
        if ok: blocked+=1
    pct=blocked/len(domains)*100
    result+=f"\n📊 {blocked}/{len(domains)} ({pct:.0f}%) — "
    result+="✅ EXCELLENT" if pct>=80 else "⚠️ GOOD" if pct>=50 else "❌ POOR"
    return result

# ==================== KEYBOARDS ====================
def get_main_keyboard(cfg=None):
    if cfg is None: cfg=load_config()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖥 CPU & RAM",      callback_data="cpu_ram"),
         InlineKeyboardButton("👥 Online Users",   callback_data="online_users")],
        [InlineKeyboardButton("📊 Traffic",        callback_data="traffic"),
         InlineKeyboardButton("🌍 My IP",          callback_data="myip")],
        [InlineKeyboardButton("🔍 Ping",           callback_data="ping"),
         InlineKeyboardButton("⚡ Speedtest",      callback_data="speedtest")],
        [InlineKeyboardButton("💿 Disk",           callback_data="disk"),
         InlineKeyboardButton("🔒 Leak Test",      callback_data="leaktest")],
        [InlineKeyboardButton("🛡 AdBlock",        callback_data="adblock"),
         InlineKeyboardButton("⚙️ Services",       callback_data="services")],
        [InlineKeyboardButton("🐳 Containers",     callback_data="containers"),
         InlineKeyboardButton("💻 Command",        callback_data="command")],
        [InlineKeyboardButton("🚫 Blokir Device",  callback_data="block_menu"),
         InlineKeyboardButton("⚙️ Settings",       callback_data="settings")],
    ])

def get_reply_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📋 Menu"),KeyboardButton("ℹ️ Help"),KeyboardButton("🔄 Refresh")]], resize_keyboard=True)

def get_services_keyboard(cfg=None):
    if cfg is None: cfg=load_config()
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("service_ctrl",cfg), callback_data="service_control")],
                                  [InlineKeyboardButton(t("back_menu",cfg), callback_data="back_to_menu")]])

def get_service_control_keyboard(cfg=None):
    if cfg is None: cfg=load_config()
    kb=[]
    for svc in ["openclash","nikki","cloudflared"]:
        kb.append([InlineKeyboardButton("▶️ Start", callback_data=f"svc_start_{svc}"),
                   InlineKeyboardButton(svc,         callback_data=f"svc_info_{svc}"),
                   InlineKeyboardButton("⏹ Stop",   callback_data=f"svc_stop_{svc}")])
        kb.append([InlineKeyboardButton(f"🔄 Restart {svc}", callback_data=f"svc_restart_{svc}")])
    kb.append([InlineKeyboardButton(t("back_menu",cfg), callback_data="back_to_menu")])
    return InlineKeyboardMarkup(kb)

def get_block_keyboard(cfg=None):
    if cfg is None: cfg=load_config()
    blocked=get_blocked_macs(); kb=[]
    for mac in blocked[:5]:
        kb.append([InlineKeyboardButton(f"✅ Izinkan {mac}", callback_data=f"unblock_{mac}")])
    kb.append([InlineKeyboardButton("🔄 Refresh", callback_data="block_menu"),
               InlineKeyboardButton("📋 Whitelist", callback_data="show_whitelist")])
    kb.append([InlineKeyboardButton(t("back_menu",cfg), callback_data="back_to_menu")])
    return InlineKeyboardMarkup(kb)

def get_settings_keyboard(cfg=None):
    if cfg is None: cfg=load_config()
    lang=cfg.get("language","id")
    def nb(key,label):
        st=cfg.get(key,True)
        return InlineKeyboardButton(f"{'🔔' if st else '🔕'} {label}", callback_data=f"toggle_{key}")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🌐 Ganti ke {'EN 🇬🇧' if lang=='id' else 'ID 🇮🇩'}", callback_data="toggle_lang")],
        [nb("notify_cpu_temp","CPU Temp"), nb("notify_ram","RAM")],
        [nb("notify_wan","WAN Alert"),     nb("notify_unknown_device","Device Asing")],
        [InlineKeyboardButton(t("back_menu",cfg), callback_data="back_to_menu")]
    ])

def get_settings_text(cfg):
    lang=cfg.get("language","id"); flag="🇮🇩" if lang=="id" else "🇬🇧"
    return (f"⚙️ <b>Pengaturan Bot</b>\n\n"
            f"{flag} Bahasa: <code>{'Indonesia' if lang=='id' else 'English'}</code>\n\n"
            f"<b>Notifikasi Otomatis:</b>\n"
            f"{'🔔' if cfg.get('notify_cpu_temp') else '🔕'} CPU Panas — batas <code>{cfg.get('cpu_temp_threshold',75)}°C</code>\n"
            f"{'🔔' if cfg.get('notify_ram') else '🔕'} RAM Penuh — batas <code>{cfg.get('ram_threshold',85)}%</code>\n"
            f"{'🔔' if cfg.get('notify_wan') else '🔕'} WAN Putus — alert jika > <code>{cfg.get('wan_timeout_minutes',60)} menit</code>\n"
            f"{'🔔' if cfg.get('notify_unknown_device') else '🔕'} Perangkat Tak Dikenal\n\n"
            f"<i>Ketuk tombol untuk toggle on/off</i>")

def get_block_menu_text(cfg):
    blocked=get_blocked_macs(); wl=cfg.get("mac_whitelist",[])
    text=(f"{t('block_title',cfg)}\n\n"
          f"📋 Whitelist diizinkan: <code>{len(wl)}</code> MAC\n"
          f"🚫 Diblokir saat ini: <code>{len(blocked)}</code> MAC\n\n")
    if blocked:
        text+="<b>MAC Terblokir:</b>\n"
        for mac in blocked[:10]: text+=f"  🔴 <code>{mac}</code>\n"
    else: text+=t("no_blocked",cfg)
    if not wl: text+=f"\n\n⚠️ {t('whitelist_empty',cfg)}"
    return text

# ==================== BACKGROUND MONITOR ====================
async def send_alert(app, message, keyboard=None):
    cfg=load_config()
    for uid in cfg.get("allowed_users",[]):
        try:
            kw={"chat_id":uid,"text":message,"parse_mode":"HTML"}
            if keyboard: kw["reply_markup"]=keyboard
            await app.bot.send_message(**kw)
        except Exception as e: logger.error(f"Alert error to {uid}: {e}")

async def monitor_loop(app):
    global monitor_state
    logger.info("Background monitor started")
    # Tunggu 30 detik setelah bot start sebelum mulai monitor
    await asyncio.sleep(30)

    while True:
        try:
            cfg=load_config(); now=datetime.now(); now_str=now.strftime("%Y-%m-%d %H:%M:%S")

            # WAN Monitor
            if cfg.get("notify_wan",True):
                wan_ok=check_wan()
                if not wan_ok:
                    if monitor_state["wan_down_since"] is None:
                        monitor_state.update({"wan_down_since":now,"wan_alert_sent":False,"wan_long_alert_sent":False})
                    if not monitor_state["wan_alert_sent"]:
                        await send_alert(app, t("wan_down_alert",cfg,time=now_str))
                        monitor_state["wan_alert_sent"]=True
                    dur=(now-monitor_state["wan_down_since"]).total_seconds()
                    timeout=cfg.get("wan_timeout_minutes",60)*60
                    if dur>=timeout and not monitor_state["wan_long_alert_sent"]:
                        await send_alert(app, t("wan_long_down",cfg,duration=format_duration(dur)))
                        monitor_state["wan_long_alert_sent"]=True
                else:
                    if monitor_state["wan_down_since"] is not None:
                        dur=(now-monitor_state["wan_down_since"]).total_seconds()
                        await send_alert(app, t("wan_up_alert",cfg,duration=format_duration(dur),time=now_str))
                    monitor_state.update({"wan_down_since":None,"wan_alert_sent":False,"wan_long_alert_sent":False})

            # CPU Temp
            if cfg.get("notify_cpu_temp",True):
                temp=get_cpu_temp(); threshold=cfg.get("cpu_temp_threshold",75)
                if temp>threshold and (time.time()-monitor_state["last_cpu_alert"])>1800:
                    await send_alert(app, t("cpu_temp_alert",cfg,temp=f"{temp:.1f}",threshold=threshold,time=now_str))
                    monitor_state["last_cpu_alert"]=time.time()

            # RAM
            if cfg.get("notify_ram",True):
                ram=get_ram_usage(); threshold=cfg.get("ram_threshold",85)
                if ram>threshold and (time.time()-monitor_state["last_ram_alert"])>1800:
                    await send_alert(app, t("ram_alert",cfg,usage=ram,threshold=threshold,time=now_str))
                    monitor_state["last_ram_alert"]=time.time()

            # Unknown Device
            if cfg.get("notify_unknown_device",True):
                wl=[m.lower() for m in cfg.get("mac_whitelist",[])]
                if wl:
                    for dev in get_current_devices():
                        mac=dev.get("mac","").lower()
                        if mac and mac not in wl and mac not in monitor_state["alerted_macs"]:
                            monitor_state["alerted_macs"].add(mac)
                            ip=dev.get("ip","?"); hn=dev.get("hostname","?")
                            kb=InlineKeyboardMarkup([[
                                InlineKeyboardButton("🚫 Blokir", callback_data=f"quick_block_{mac}_{ip}"),
                                InlineKeyboardButton("✅ Izinkan", callback_data=f"quick_allow_{mac}")
                            ]])
                            await send_alert(app, t("unknown_device",cfg,mac=mac,ip=ip,hostname=hn,time=now_str), keyboard=kb)

        except Exception as e: logger.error(f"Monitor error: {e}")
        await asyncio.sleep(60)

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized!"); return
    cfg=load_config()
    await update.message.reply_text(t("welcome",cfg), reply_markup=get_main_keyboard(cfg), parse_mode='HTML')
    await update.message.reply_text(t("nav_hint",cfg), reply_markup=get_reply_keyboard())

async def handle_keyboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id): return
    cfg=load_config(); text=update.message.text
    if text=="📋 Menu":
        await update.message.reply_text(t("menu",cfg), parse_mode='HTML', reply_markup=get_main_keyboard(cfg))
    elif text=="ℹ️ Help":
        await update.message.reply_text(get_help_text(cfg), parse_mode='HTML')
    elif text=="🔄 Refresh":
        await update.message.reply_text(t("refreshed",cfg), parse_mode='HTML', reply_markup=get_main_keyboard(cfg))

def get_help_text(cfg=None):
    if cfg is None: cfg=load_config()
    return ("🤖 <b>PANDUAN MONITORING BOT</b>\n\n"
            "<b>MENU:</b>\n"
            "• 🖥 CPU & RAM • 👥 Online Users • 📊 Traffic\n"
            "• 🌍 My IP • 🔍 Ping • ⚡ Speedtest\n"
            "• 💿 Disk • 🔒 Leak Test • 🛡 AdBlock\n"
            "• ⚙️ Services • 🐳 Containers\n"
            "• 🚫 Blokir Device — blokir MAC tak dikenal\n"
            "• ⚙️ Settings — bahasa & notifikasi\n\n"
            "<b>NOTIFIKASI OTOMATIS:</b>\n"
            "• 🌡 CPU panas | 💾 RAM penuh\n"
            "• 📡 WAN putus/nyambung\n"
            "• ⚠️ Device tak dikenal di jaringan\n\n"
            "<b>COMMAND:</b>\n<code>/cmd uptime</code>")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    if not check_auth(query.from_user.id): await query.answer("❌ Unauthorized!"); return
    await query.answer()
    data=query.data; cfg=load_config()

    if data=="back_to_menu":
        await query.edit_message_text(t("menu",cfg), parse_mode='HTML', reply_markup=get_main_keyboard(cfg)); return

    if data=="settings":
        await query.edit_message_text(get_settings_text(cfg), parse_mode='HTML', reply_markup=get_settings_keyboard(cfg)); return

    if data=="toggle_lang":
        cfg["language"]="en" if cfg.get("language","id")=="id" else "id"
        save_config(cfg)
        await query.edit_message_text(get_settings_text(cfg), parse_mode='HTML', reply_markup=get_settings_keyboard(cfg)); return

    if data.startswith("toggle_notify"):
        key=data.replace("toggle_","")
        cfg[key]=not cfg.get(key,True); save_config(cfg)
        await query.edit_message_text(get_settings_text(cfg), parse_mode='HTML', reply_markup=get_settings_keyboard(cfg)); return

    if data=="block_menu":
        await query.edit_message_text(get_block_menu_text(cfg), parse_mode='HTML', reply_markup=get_block_keyboard(cfg)); return

    if data=="show_whitelist":
        wl=cfg.get("mac_whitelist",[])
        text="📋 <b>MAC Whitelist:</b>\n\n"+"\n".join(f"✅ <code>{m}</code>" for m in wl) if wl else t("whitelist_empty",cfg)
        await query.edit_message_text(text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back_menu",cfg), callback_data="block_menu")]])); return

    if data.startswith("unblock_"):
        mac=data[8:]; unblock_mac(mac)
        cfg2=load_config()
        await query.edit_message_text(t("device_unblocked",cfg2,mac=mac), parse_mode='HTML', reply_markup=get_block_keyboard(cfg2)); return

    if data.startswith("quick_block_"):
        parts=data.split("_",3); mac=parts[2]; ip=parts[3] if len(parts)>3 else "?"
        block_mac(mac); monitor_state["alerted_macs"].discard(mac)
        await query.edit_message_text(t("device_blocked",cfg,mac=mac,ip=ip), parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back_menu",cfg), callback_data="back_to_menu")]])); return

    if data.startswith("quick_allow_"):
        mac=data[12:]; wl=cfg.get("mac_whitelist",[])
        if mac not in wl: wl.append(mac); cfg["mac_whitelist"]=wl; save_config(cfg)
        await query.edit_message_text(t("device_unblocked",cfg,mac=mac), parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back_menu",cfg), callback_data="back_to_menu")]])); return

    if data=="service_control":
        await query.edit_message_text("🔧 <b>SERVICE CONTROL</b>\n\n▶️ Start | ⏹ Stop | 🔄 Restart",
            parse_mode='HTML', reply_markup=get_service_control_keyboard(cfg)); return

    if data.startswith("svc_"):
        parts=data.split("_",2)
        if len(parts)>=3:
            action=parts[1]; svc=parts[2]
            if action=="info":
                st=run_command(f"service {svc} status 2>&1")
                await query.edit_message_text(f"⚙️ <b>{svc}</b>\n\n<code>{st}</code>",
                    parse_mode='HTML', reply_markup=get_service_control_keyboard(cfg)); return
            loading=await query.edit_message_text(t("processing",cfg))
            result=service_control(svc,action)
            await loading.edit_text(result, parse_mode='HTML', reply_markup=get_service_control_keyboard(cfg))
        return

    loading=await query.edit_message_text(t("loading",cfg))
    try:
        handler_map={
            "cpu_ram":(get_cpu_ram_info,get_main_keyboard),
            "online_users":(get_online_users,get_main_keyboard),
            "traffic":(get_vnstat_traffic,get_main_keyboard),
            "myip":(get_my_ip,get_main_keyboard),
            "ping":(ping_test,get_main_keyboard),
            "speedtest":(speedtest,get_main_keyboard),
            "disk":(get_disk_info,get_main_keyboard),
            "leaktest":(leak_test,get_main_keyboard),
            "adblock":(adblock_test,get_main_keyboard),
            "services":(check_services,get_services_keyboard),
            "containers":(get_container_info,get_main_keyboard),
        }
        if data=="command":
            await loading.edit_text("💻 <b>Command Mode</b>\n\nFormat: <code>/cmd perintah</code>",
                parse_mode='HTML', reply_markup=get_main_keyboard(cfg)); return
        if data in handler_map:
            fn,kb_fn=handler_map[data]; result=fn(); keyboard=kb_fn(cfg)
        else:
            result="Unknown command"; keyboard=get_main_keyboard(cfg)
        if len(result)>4000:
            chunks=[result[i:i+4000] for i in range(0,len(result),4000)]
            await loading.edit_text(chunks[0], parse_mode='HTML', reply_markup=keyboard)
            for chunk in chunks[1:]: await query.message.reply_text(chunk, parse_mode='HTML')
        else:
            await loading.edit_text(result, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await loading.edit_text(f"{t('error',cfg)}: {str(e)}", parse_mode='HTML', reply_markup=get_main_keyboard(cfg))

async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id): await update.message.reply_text("❌ Unauthorized!"); return
    cfg=load_config()
    if not context.args: await update.message.reply_text(t("cmd_format",cfg), parse_mode='HTML'); return
    command=' '.join(context.args)
    if any(c in command.lower() for c in ['rm -rf','dd if=','mkfs','format','> /dev/']):
        await update.message.reply_text(t("cmd_blocked",cfg)); return
    loading=await update.message.reply_text(t("executing",cfg))
    result=run_command(command)
    if len(result)>4000: result=result[:4000]+"...(truncated)"
    await loading.edit_text(f"💻 <b>Command:</b> <code>{command}</code>\n\n<b>Output:</b>\n<code>{result}</code>", parse_mode='HTML')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# ==================== MAIN ====================
def main():
    cfg=load_config()
    if not cfg.get("bot_token",""):
        logger.error("BOT_TOKEN tidak dikonfigurasi! Edit /etc/remotbot/config.json"); return

    app=Application.builder().token(cfg["bot_token"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cmd", cmd_handler))
    app.add_handler(MessageHandler(filters.Regex('^(📋 Menu|ℹ️ Help|🔄 Refresh)$'), handle_keyboard_button))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    async def post_init(application):
        asyncio.create_task(monitor_loop(application))

    app.post_init=post_init
    logger.info("RemotWRT Bot started with background monitor!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
