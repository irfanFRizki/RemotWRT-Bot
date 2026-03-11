#!/usr/bin/env python3
"""
OpenWRT Telegram Monitoring Bot untuk Raspberry Pi 4
Requirements: pip install python-telegram-bot requests psutil
"""

import asyncio
import logging
import subprocess
import json
import os
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==================== KONFIGURASI ====================
CONFIG_FILE = "/etc/remotbot/config.json"

def load_config():
    """Load konfigurasi dari file JSON"""
    default_config = {
        "bot_token": "",
        "allowed_users": [],
        "cgi_online_path": "/www/cgi-bin/online"
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
                return {**default_config, **cfg}
    except Exception as e:
        logger_pre.error(f"Failed to load config: {e}")
    return default_config

# Pre-setup logger untuk load_config
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger_pre = logging.getLogger("config")

CONFIG = load_config()
BOT_TOKEN = CONFIG.get("bot_token", "")
ALLOWED_USERS = CONFIG.get("allowed_users", [])
CGI_ONLINE_PATH = CONFIG.get("cgi_online_path", "/www/cgi-bin/online")

# ==================== SETUP LOGGING ====================
logger = logging.getLogger(__name__)

# ==================== FUNGSI UTILITAS ====================

def check_auth(user_id: int) -> bool:
    """Cek apakah user diizinkan menggunakan bot"""
    # Reload config setiap cek agar perubahan settings langsung aktif
    cfg = load_config()
    allowed = cfg.get("allowed_users", [])
    return user_id in allowed

def run_command(command: str) -> str:
    """Jalankan command shell dan return output"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Error: Command timeout"
    except Exception as e:
        return f"Error: {str(e)}"

# ==================== FUNGSI MONITORING ====================

def get_cpu_ram_info() -> str:
    """Dapatkan info CPU dan RAM menggunakan sysinfo.sh"""
    try:
        sysinfo_check = run_command("which sysinfo.sh")
        if sysinfo_check:
            result = run_command("sysinfo.sh --plain")
            lines = result.split('\n')
            output_lines = []
            capture = False
            for line in lines:
                if '=== System Info ===' in line:
                    capture = True
                if capture and 'RAM Available:' in line:
                    output_lines.append(line)
                    break
                if '=== Disk Usage ===' in line or '=== Network Interfaces ===' in line or '=== System Time ===' in line:
                    break
                if capture:
                    output_lines.append(line)
            result = '\n'.join(output_lines)
            result = "🖥 <b>CPU & RAM Status</b>\n\n" + result
            for header in ["System Info", "CPU Temperature", "CPU Usage", "Load Average", "CPU Info", "Memory (RAM)", "Swap"]:
                result = result.replace(f"=== {header} ===", f"<b>=== {header} ===</b>")
            return result
        else:
            temp_raw = run_command("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
            temp = float(temp_raw) / 1000 if temp_raw.replace('.','').isdigit() else 0
            load = run_command("cat /proc/loadavg").split()[:3]
            cpu_usage = run_command("top -bn1 | grep 'CPU:' | sed 's/CPU://g' | awk '{print $1}'") or "N/A"
            mem_info = run_command("free | grep Mem")
            mem_parts = mem_info.split()
            if len(mem_parts) >= 4:
                total = int(mem_parts[1])
                used = int(mem_parts[2])
                free = int(mem_parts[3])
                total_mb = total // 1024
                used_mb = used // 1024
                free_mb = free // 1024
                usage_pct = int((used / total) * 100) if total > 0 else 0
                return (
                    f"🖥 <b>CPU & RAM Status</b>\n\n"
                    f"🌡 Temperature: <code>{temp:.0f}°C</code>\n"
                    f"📊 CPU Usage: <code>{cpu_usage}%</code>\n"
                    f"⚡ Load Average: <code>{' '.join(load)}</code>\n"
                    f"💾 RAM Used: <code>{usage_pct}% ({used_mb} MB / {total_mb} MB)</code>\n"
                    f"💾 RAM Free: <code>{free_mb} MB</code>"
                )
    except Exception as e:
        return f"Error: {str(e)}"
    return "Error: Unable to get system info"

def get_online_users() -> str:
    cfg = load_config()
    cgi_path = cfg.get("cgi_online_path", "/www/cgi-bin/online")
    try:
        result = subprocess.run(["bash", cgi_path], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return "Error: Failed to execute online script"
        output_lines = result.stdout.strip().split('\n')
        json_start = next((i for i, line in enumerate(output_lines) if line.strip().startswith('[')), -1)
        if json_start == -1:
            return "Error: Invalid output format"
        json_data = '\n'.join(output_lines[json_start:])
        devices = json.loads(json_data)
        if not devices:
            return "👥 <b>Online Users</b>\n\nTidak ada perangkat online"
        status_emoji = {"TERHUBUNG": "🟢","TERHUBUNG TIDAK AKTIF": "🟡","TIDAK DIKETAHUI": "🟠","TIDAK TERHUBUNG": "🔴"}
        result_text = "👥 <b>Online Users</b>\n\n"
        for idx, device in enumerate(devices, 1):
            emoji = status_emoji.get(device['status'], '⚪')
            hostname = device['hostname'] if device['hostname'] != '*' else 'Unknown'
            result_text += (
                f"{idx}. {emoji} <b>{hostname}</b>\n"
                f"   IP: <code>{device['ip']}</code>\n"
                f"   MAC: <code>{device['mac']}</code>\n"
                f"   Status: {device['status']}\n\n"
            )
        return result_text
    except Exception as e:
        return f"Error: {str(e)}"

def get_vnstat_traffic() -> str:
    try:
        def format_bytes(bytes_val):
            if bytes_val < 1024: return f"{bytes_val} B"
            elif bytes_val < 1024*1024: return f"{bytes_val/1024:.2f} KB"
            elif bytes_val < 1024*1024*1024: return f"{bytes_val/(1024*1024):.2f} MB"
            else: return f"{bytes_val/(1024*1024*1024):.2f} GB"

        result_text = "📊 <b>Traffic Statistics (eth1)</b>\n\n"
        try:
            cgi_result = subprocess.run(["sh", "/www/cgi-bin/traffic"], capture_output=True, text=True, timeout=10)
            if cgi_result.returncode == 0:
                output_lines = cgi_result.stdout.strip().split('\n')
                json_start = next((i for i, line in enumerate(output_lines) if line.strip().startswith('{')), -1)
                if json_start != -1:
                    traffic_data = json.loads('\n'.join(output_lines[json_start:]))
                    if "error" not in traffic_data:
                        rx_bytes = int(traffic_data.get('rx', 0))
                        tx_bytes = int(traffic_data.get('tx', 0))
                        result_text += f"📡 <b>Live (3 detik):</b>\n⬇️ RX: <code>{format_bytes(rx_bytes)}</code>\n⬆️ TX: <code>{format_bytes(tx_bytes)}</code>\n\n"
        except: pass

        for period, flag, label in [('d', 'day', '📅 <b>Hari ini:</b>'), ('m', 'month', '📈 <b>Bulan ini:</b>')]:
            try:
                data = json.loads(run_command(f"vnstat --json {period} -i eth1"))
                if data and 'interfaces' in data:
                    items = data['interfaces'][0]['traffic'][flag]
                    if items:
                        last = items[-1]
                        rx, tx = last['rx'], last['tx']
                        result_text += f"{label}\n⬇️ RX: <code>{format_bytes(rx)}</code>\n⬆️ TX: <code>{format_bytes(tx)}</code>\n📊 Total: <code>{format_bytes(rx+tx)}</code>\n\n"
            except: pass

        try:
            top_data = json.loads(run_command("vnstat --json t -i eth1"))
            if top_data and 'interfaces' in top_data:
                top_days = top_data['interfaces'][0]['traffic']['top'][:5]
                if top_days:
                    result_text += "🏆 <b>Top 5 Hari Tertinggi:</b>\n"
                    for idx, day in enumerate(top_days, 1):
                        date = f"{day['date']['year']}-{day['date']['month']:02d}-{day['date']['day']:02d}"
                        result_text += f"{idx}. <code>{date}</code>: {format_bytes(day['rx']+day['tx'])}\n"
        except: pass

        return result_text.strip() if result_text != "📊 <b>Traffic Statistics (eth1)</b>\n\n" else "Error: Unable to get traffic data"
    except Exception as e:
        return f"Error: {str(e)}"

def get_my_ip() -> str:
    try:
        for service in ["https://api.ipify.org","https://ifconfig.me","https://icanhazip.com"]:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    ip = response.text.strip()
                    try:
                        info = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5).json()
                        return (f"🌍 <b>Public IP Information</b>\n\nIP: <code>{ip}</code>\nISP: <code>{info.get('org','N/A')}</code>\nLocation: <code>{info.get('city','N/A')}, {info.get('region','N/A')}</code>\nCountry: <code>{info.get('country','N/A')}</code>")
                    except:
                        return f"🌍 <b>Public IP:</b> <code>{ip}</code>"
            except: continue
        return "Error: Unable to get public IP"
    except Exception as e:
        return f"Error: {str(e)}"

def ping_test(host: str = "8.8.8.8") -> str:
    try:
        result = run_command(f"ping -c 4 {host}")
        stats = [line for line in result.split('\n') if 'min/avg/max' in line or 'packet loss' in line]
        return f"🔍 <b>Ping Test ({host})</b>\n\n<code>{chr(10).join(stats)}</code>"
    except Exception as e:
        return f"Error: {str(e)}"

def speedtest() -> str:
    try:
        for binary, label in [("/usr/bin/speedtest-ookla","Ookla"),("/usr/bin/speedtest","Auto")]:
            check = run_command(f"test -f {binary} && echo 'OK'")
            if check:
                result = run_command(f"timeout 60 {binary} --accept-license --accept-gdpr 2>&1")
                if "timeout" in result.lower():
                    return "⚡ <b>Speedtest</b>\n\nError: Test timeout (>60 detik)"
                lines = result.split('\n')
                server=ping=download=upload=""
                for line in lines:
                    if "Server:" in line: server = line.split("Server:")[1].strip()
                    elif "Latency:" in line or "Idle Latency:" in line:
                        parts = line.split(":")
                        if len(parts) > 1: ping = parts[-1].strip().split()[0] if parts[-1].strip() else ""
                    elif "Download:" in line: download = line.split("Download:")[1].strip()
                    elif "Upload:" in line: upload = line.split("Upload:")[1].strip()
                txt = f"⚡ <b>Speedtest Results</b>\n<i>Powered by {label}</i>\n\n"
                if server: txt += f"🌐 Server: <code>{server}</code>\n"
                if ping: txt += f"📶 Latency: <code>{ping} ms</code>\n"
                if download: txt += f"⬇️ Download: <code>{download}</code>\n"
                if upload: txt += f"⬆️ Upload: <code>{upload}</code>\n"
                if not any([server,ping,download,upload]): txt += f"\n<code>{result[:500]}</code>"
                return txt
        check_cli = run_command("which speedtest-cli 2>/dev/null")
        if check_cli:
            result = run_command("timeout 60 speedtest-cli --simple 2>&1")
            lines = result.split('\n')
            ping=download=upload=""
            for line in lines:
                if "Ping:" in line: ping=line.split("Ping:")[1].strip()
                elif "Download:" in line: download=line.split("Download:")[1].strip()
                elif "Upload:" in line: upload=line.split("Upload:")[1].strip()
            return f"⚡ <b>Speedtest Results</b>\n<i>Powered by speedtest-cli</i>\n\n📶 Ping: <code>{ping or 'N/A'}</code>\n⬇️ Download: <code>{download or 'N/A'}</code>\n⬆️ Upload: <code>{upload or 'N/A'}</code>"
        return ("⚠️ <b>Speedtest Tool Not Found</b>\n\n"
                "Install: <code>opkg install python3-pip && pip3 install speedtest-cli</code>")
    except Exception as e:
        return f"Error: {str(e)}"

def get_disk_info() -> str:
    try:
        result = "💿 <b>Disk Usage</b>\n\n"
        found = False
        for disk in ["sda1","sdb1","root","mmcblk0p3"]:
            info = run_command(f"df -h | grep {disk}")
            if info:
                parts = info.split()
                if len(parts) >= 5:
                    result += f"<b>{disk}:</b>\nSize: <code>{parts[1]}</code>\nUsed: <code>{parts[2]}</code>\nFree: <code>{parts[3]}</code>\nUsage: <code>{parts[4]}</code>\n\n"
                    found = True
        if not found: result += "No disk found"
        return result.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def leak_test() -> str:
    try:
        result_text = "🔒 <b>Leak Test</b>\n\n"
        try:
            public_ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
            result_text += f"🌍 <b>Public IP:</b> <code>{public_ip}</code>\n\n"
        except:
            public_ip = "unknown"
            result_text += "🌍 <b>Public IP:</b> Unable to fetch\n\n"
        result_text += "🔍 <b>DNS Leak Test:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for domain, name in [("whoami.akamai.net","Akamai"),("o-o.myaddr.l.google.com","Google"),("myip.opendns.com","OpenDNS")]:
            dns_result = run_command(f"nslookup {domain} 2>&1")
            resolved_ip = None
            for line in dns_result.split('\n'):
                if 'Address' in line and '127.0.0.1' not in line and '#53' not in line:
                    parts = line.split()
                    if len(parts) >= 2: resolved_ip = parts[-1]; break
            result_text += f"• {name}: <code>{resolved_ip}</code>\n" if resolved_ip else f"• {name}: <i>Unable to resolve</i>\n"
        result_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        dns_server = run_command("cat /etc/resolv.conf | grep nameserver | head -1 | awk '{print $2}'")
        if dns_server: result_text += f"📡 <b>DNS Server:</b> <code>{dns_server}</code>\n\n"
        result_text += "🛡 <b>VPN/Proxy Detection:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        try:
            ip_info = requests.get(f"http://ip-api.com/json/{public_ip}", timeout=5).json()
            if ip_info.get("status") == "success":
                result_text += ("✅ <b>Status:</b> VPN/Proxy detected\n" if ip_info.get("proxy") or ip_info.get("hosting") else "⚠️ <b>Status:</b> Direct connection\n")
                result_text += f"📍 <b>Location:</b> <code>{ip_info.get('city','N/A')}, {ip_info.get('country','N/A')}</code>\n🏢 <b>ISP:</b> <code>{ip_info.get('isp','N/A')}</code>\n"
        except: result_text += "ℹ️ Unable to check VPN status\n"
        return result_text
    except Exception as e:
        return f"Error: {str(e)}"

def adblock_test() -> str:
    try:
        result = "🛡 <b>AdBlock Test</b>\n\n<b>Testing Ad Domains:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        test_domains = [("ads.google.com","Google Ads"),("doubleclick.net","DoubleClick"),("googleadservices.com","Google Ad Services"),("googlesyndication.com","Google Syndication"),("adservice.google.com","Ad Service"),("pagead2.googlesyndication.com","Page Ads"),("static.ads-twitter.com","Twitter Ads")]
        blocked = 0
        for domain, name in test_domains:
            dns_check = run_command(f"nslookup {domain.split('/')[0]} 2>&1")
            is_blocked = "NXDOMAIN" in dns_check or "0.0.0.0" in dns_check or "127.0.0.1" in dns_check or "can't resolve" in dns_check.lower()
            result += f"{'✅' if is_blocked else '❌'} {name}\n"
            if is_blocked: blocked += 1
        total = len(test_domains)
        pct = (blocked/total*100) if total > 0 else 0
        result += f"━━━━━━━━━━━━━━━━━━━━\n\n📊 <b>Summary:</b>\nBlocked: {blocked}/{total} ({pct:.1f}%)\n"
        result += "\n✅ <b>AdBlock: EXCELLENT</b>" if pct>=80 else "\n⚠️ <b>AdBlock: GOOD</b>" if pct>=50 else "\n❌ <b>AdBlock: POOR</b>"
        return result
    except Exception as e:
        return f"Error: {str(e)}"

def check_services() -> str:
    try:
        services = ["openclash","nikki","cloudflared"]
        result = "⚙️ <b>Services Status</b>\n\n"
        for service in services:
            status = run_command(f"service {service} status 2>&1").lower()
            if "running" in status: result += f"✅ <b>{service}:</b> RUNNING\n"
            elif "active" in status: result += f"✅ <b>{service}:</b> ACTIVE\n"
            elif "inactive" in status or "stopped" in status: result += f"❌ <b>{service}:</b> STOPPED\n"
            elif "not found" in status or "usage" in status: result += f"❓ <b>{service}:</b> NOT INSTALLED\n"
            else:
                ps_check = run_command(f"ps | grep {service} | grep -v grep")
                result += f"{'✅' if ps_check else '❌'} <b>{service}:</b> {'RUNNING' if ps_check else 'STOPPED'}\n"
        result += "\n💡 <i>Klik 'Service Control' untuk manage services</i>"
        return result
    except Exception as e:
        return f"Error: {str(e)}"

def get_container_info() -> str:
    try:
        result = "🐳 <b>Container Information</b>\n\n"
        tool = run_command("which docker") and "docker" or run_command("which podman") and "podman" or None
        if not tool: return result + "❌ Docker/Podman not installed"
        containers = run_command(f"{tool} ps -a --format '{{{{.Names}}}}|{{{{.Status}}}}|{{{{.Image}}}}'")
        if containers and "Error" not in containers:
            result += f"<b>{tool.capitalize()} Containers:</b>\n"
            for line in containers.split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        status_emoji = "🟢" if "Up" in parts[1] else "🔴"
                        result += f"{status_emoji} <b>{parts[0]}</b>\n   Image: <code>{parts[2]}</code>\n   Status: <code>{parts[1]}</code>\n\n"
        else:
            result += f"No {tool.capitalize()} containers found\n\n"
        return result
    except Exception as e:
        return f"Error: {str(e)}"

def service_control(service_name: str, action: str) -> str:
    try:
        if action not in ["start","stop","restart"]:
            return "❌ Invalid action. Use: start, stop, restart"
        result = run_command(f"service {service_name} {action} 2>&1")
        import time; time.sleep(2)
        status = run_command(f"service {service_name} status 2>&1")
        return (f"⚙️ <b>Service Control</b>\n\nService: <code>{service_name}</code>\nAction: <code>{action}</code>\n\n<b>Result:</b>\n<code>{result}</code>\n\n<b>Current Status:</b>\n<code>{status}</code>")
    except Exception as e:
        return f"Error: {str(e)}"

# ==================== KEYBOARD ====================

def get_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🖥 CPU & RAM", callback_data="cpu_ram"), InlineKeyboardButton("👥 Online Users", callback_data="online_users")],
        [InlineKeyboardButton("📊 Traffic", callback_data="traffic"), InlineKeyboardButton("🌍 My IP", callback_data="myip")],
        [InlineKeyboardButton("🔍 Ping", callback_data="ping"), InlineKeyboardButton("⚡ Speedtest", callback_data="speedtest")],
        [InlineKeyboardButton("💿 Disk", callback_data="disk"), InlineKeyboardButton("🔒 Leak Test", callback_data="leaktest")],
        [InlineKeyboardButton("🛡 AdBlock", callback_data="adblock"), InlineKeyboardButton("⚙️ Services", callback_data="services")],
        [InlineKeyboardButton("🐳 Containers", callback_data="containers"), InlineKeyboardButton("💻 Command", callback_data="command")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reply_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📋 Menu"), KeyboardButton("ℹ️ Help"), KeyboardButton("🔄 Refresh")]], resize_keyboard=True)

def get_services_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Service Control", callback_data="service_control")],[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]])

def get_service_control_keyboard() -> InlineKeyboardMarkup:
    services = ["openclash","nikki","cloudflared"]
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(f"▶️ Start", callback_data=f"svc_start_{service}"), InlineKeyboardButton(f"{service}", callback_data=f"svc_info_{service}"), InlineKeyboardButton(f"⏹ Stop", callback_data=f"svc_stop_{service}")])
        keyboard.append([InlineKeyboardButton(f"🔄 Restart {service}", callback_data=f"svc_restart_{service}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_containers_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]])

# ==================== HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_auth(user_id):
        await update.message.reply_text("❌ Unauthorized access!")
        return
    await update.message.reply_text(
        "🤖 <b>OpenWRT Monitoring Bot</b>\n\nSelamat datang di bot monitoring untuk Raspberry Pi 4 OpenWRT!\n\nPilih menu di bawah untuk melihat informasi:",
        reply_markup=get_main_keyboard(), parse_mode='HTML')
    await update.message.reply_text("Gunakan tombol di bawah untuk navigasi cepat:", reply_markup=get_reply_keyboard())

async def handle_keyboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_auth(user_id): return
    text = update.message.text
    if text == "📋 Menu":
        await update.message.reply_text("📋 <b>MENU UTAMA</b>\n\nPilih menu yang Anda inginkan:", parse_mode='HTML', reply_markup=get_main_keyboard())
    elif text == "ℹ️ Help":
        await update.message.reply_text(get_help_text(), parse_mode='HTML')
    elif text == "🔄 Refresh":
        await update.message.reply_text("🔄 <b>System Refreshed!</b>\n\nSilakan pilih menu untuk melihat data terbaru.", parse_mode='HTML', reply_markup=get_main_keyboard())

def get_help_text():
    return (
        "🤖 <b>PANDUAN MONITORING BOT</b>\n\n<b>MENU TERSEDIA:</b>\n"
        "• 🖥 CPU & RAM - Info CPU dan memory\n• 👥 Online Users - Daftar device online\n"
        "• 📊 Traffic - Statistik bandwidth\n• 🌍 My IP - Info IP public\n"
        "• 🔍 Ping - Test koneksi\n• ⚡ Speedtest - Test kecepatan internet\n"
        "• 💿 Disk - Info disk usage\n• 🔒 Leak Test - DNS/IP leak test\n"
        "• 🛡 AdBlock - Test adblock\n• ⚙️ Services - Status services\n"
        "• 🐳 Containers - Info Docker/Podman\n• 🔧 Service Control - Start/Stop/Restart\n"
        "• 💻 Command - Jalankan command custom\n\n"
        "<b>CUSTOM COMMAND:</b>\nFormat: <code>/cmd your_command</code>\n"
        "Contoh: <code>/cmd uptime</code>"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not check_auth(user_id):
        await query.answer("❌ Unauthorized!")
        return
    await query.answer()
    callback_data = query.data

    if callback_data == "back_to_menu":
        await query.edit_message_text(text="📋 <b>MENU UTAMA</b>\n\nPilih menu yang Anda inginkan:", parse_mode='HTML', reply_markup=get_main_keyboard())
        return

    if callback_data.startswith("svc_"):
        parts = callback_data.split("_")
        if len(parts) >= 3:
            action = parts[1]
            service = "_".join(parts[2:])
            if action == "info":
                status = run_command(f"service {service} status 2>&1")
                await query.edit_message_text(text=f"⚙️ <b>Service Info</b>\n\nService: <code>{service}</code>\n\n<b>Current Status:</b>\n<code>{status}</code>", parse_mode='HTML', reply_markup=get_service_control_keyboard())
                return
            loading_msg = await query.edit_message_text("⏳ Processing...")
            result = service_control(service, action)
            await loading_msg.edit_text(result, parse_mode='HTML', reply_markup=get_service_control_keyboard())
        return

    if callback_data == "service_control":
        await query.edit_message_text(text="🔧 <b>SERVICE CONTROL</b>\n\nPilih action untuk service:\n▶️ Start | ⏹ Stop | 🔄 Restart\n\nKlik nama service untuk melihat status.", parse_mode='HTML', reply_markup=get_service_control_keyboard())
        return

    loading_msg = await query.edit_message_text(text="⏳ Loading...")
    try:
        handler_map = {
            "cpu_ram": (get_cpu_ram_info, get_main_keyboard),
            "online_users": (get_online_users, get_main_keyboard),
            "traffic": (get_vnstat_traffic, get_main_keyboard),
            "myip": (get_my_ip, get_main_keyboard),
            "ping": (ping_test, get_main_keyboard),
            "speedtest": (speedtest, get_main_keyboard),
            "disk": (get_disk_info, get_main_keyboard),
            "leaktest": (leak_test, get_main_keyboard),
            "adblock": (adblock_test, get_main_keyboard),
            "services": (check_services, get_services_keyboard),
            "containers": (get_container_info, get_containers_keyboard),
        }
        if callback_data == "command":
            await loading_msg.edit_text("💻 <b>Command Mode</b>\n\nKirim command dengan format:\n<code>/cmd your_command_here</code>\n\nContoh:\n<code>/cmd uptime</code>\n<code>/cmd ip addr</code>", parse_mode='HTML', reply_markup=get_main_keyboard())
            return
        if callback_data in handler_map:
            fn, kb_fn = handler_map[callback_data]
            result = fn()
            keyboard = kb_fn()
        else:
            result = "Unknown command"
            keyboard = get_main_keyboard()

        if len(result) > 4000:
            chunks = [result[i:i+4000] for i in range(0, len(result), 4000)]
            await loading_msg.edit_text(text=chunks[0], parse_mode='HTML', reply_markup=keyboard)
            for chunk in chunks[1:]:
                await query.message.reply_text(text=chunk, parse_mode='HTML')
        else:
            await loading_msg.edit_text(result, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in button_callback: {e}")
        await loading_msg.edit_text(text=f"❌ Terjadi kesalahan: {str(e)}", parse_mode='HTML', reply_markup=get_main_keyboard())

async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_auth(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    if not context.args:
        await update.message.reply_text("❌ Format: <code>/cmd your_command</code>", parse_mode='HTML')
        return
    command = ' '.join(context.args)
    blacklist = ['rm -rf','dd if=','mkfs','format','> /dev/']
    if any(cmd in command.lower() for cmd in blacklist):
        await update.message.reply_text("❌ Dangerous command blocked!")
        return
    loading_msg = await update.message.reply_text("⏳ Executing...")
    result = run_command(command)
    if len(result) > 4000: result = result[:4000] + "\n\n... (truncated)"
    await loading_msg.edit_text(f"💻 <b>Command:</b> <code>{command}</code>\n\n<b>Output:</b>\n<code>{result}</code>", parse_mode='HTML')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def main():
    cfg = load_config()
    token = cfg.get("bot_token","")
    if not token:
        logger.error("BOT_TOKEN not configured! Edit /etc/remotbot/config.json")
        return
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cmd", cmd_handler))
    application.add_handler(MessageHandler(filters.Regex('^(📋 Menu|ℹ️ Help|🔄 Refresh)$'), handle_keyboard_button))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    logger.info("RemotWRT Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
