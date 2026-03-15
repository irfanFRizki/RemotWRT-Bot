#!/usr/bin/env python3
"""
OpenWRT Telegram Monitoring Bot untuk Raspberry Pi 4
Config dibaca dari UCI: /etc/config/remotbot
Set token: uci set remotbot.main.bot_token='TOKEN'
           uci set remotbot.main.allowed_users='USER_ID'
           uci commit remotbot
"""

import asyncio
import logging
import subprocess
import json
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==================== BACA KONFIGURASI DARI UCI ====================

def uci_get(key: str, default: str = "") -> str:
    try:
        result = subprocess.run(["uci", "get", key], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return default

def load_config():
    bot_token    = uci_get("remotbot.main.bot_token", "")
    allowed_str  = uci_get("remotbot.main.allowed_users", "")
    cgi_online   = uci_get("remotbot.main.cgi_online_path", "/www/cgi-bin/online")
    allowed_users = []
    for uid in allowed_str.replace(",", " ").split():
        uid = uid.strip()
        if uid.lstrip("-").isdigit():
            allowed_users.append(int(uid))
    return bot_token, allowed_users, cgi_online

BOT_TOKEN, ALLOWED_USERS, CGI_ONLINE_PATH = load_config()

if not BOT_TOKEN:
    import sys
    print("ERROR: Bot token belum dikonfigurasi!")
    print("Jalankan:")
    print("  uci set remotbot.main.bot_token='TOKEN_KAMU'")
    print("  uci set remotbot.main.allowed_users='USER_ID_KAMU'")
    print("  uci set remotbot.main.enabled='1'")
    print("  uci commit remotbot")
    print("  /etc/init.d/remotbot start")
    sys.exit(1)

# ==================== SETUP LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== FUNGSI UTILITAS ====================

def check_auth(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def run_command(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Error: Command timeout"
    except Exception as e:
        return f"Error: {str(e)}"

# ==================== FUNGSI MONITORING ====================

def get_cpu_ram_info() -> str:
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
                if '=== Disk Usage ===' in line or '=== Network Interfaces ===' in line:
                    break
                if capture:
                    output_lines.append(line)
            result = '\n'.join(output_lines)
            result = "🖥 <b>CPU & RAM Status</b>\n\n" + result
            for h in ["System Info","CPU Temperature","CPU Usage","Load Average","CPU Info","Memory (RAM)","Swap"]:
                result = result.replace(f"=== {h} ===", f"<b>=== {h} ===</b>")
            return result
        temp_raw = run_command("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
        temp = float(temp_raw) / 1000 if temp_raw.replace('.','').isdigit() else 0
        load = run_command("cat /proc/loadavg").split()[:3]
        cpu_usage = run_command("top -bn1 | grep 'CPU:' | sed 's/CPU://g' | awk '{print $1}'") or "N/A"
        mem_info = run_command("free | grep Mem")
        mem_parts = mem_info.split()
        if len(mem_parts) >= 4:
            total, used, free = int(mem_parts[1]), int(mem_parts[2]), int(mem_parts[3])
            usage_pct = int((used / total) * 100) if total > 0 else 0
            return (
                f"🖥 <b>CPU & RAM Status</b>\n\n"
                f"🌡 Temperature: <code>{temp:.0f}°C</code>\n"
                f"📊 CPU Usage: <code>{cpu_usage}%</code>\n"
                f"⚡ Load Average: <code>{' '.join(load)}</code>\n"
                f"💾 RAM Used: <code>{usage_pct}% ({used//1024} MB / {total//1024} MB)</code>\n"
                f"💾 RAM Free: <code>{free//1024} MB</code>"
            )
    except Exception as e:
        return f"Error: {str(e)}"
    return "Error: Unable to get system info"

def get_online_users() -> str:
    try:
        result = subprocess.run(["bash", CGI_ONLINE_PATH], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return "Error: Failed to execute online script"
        lines = result.stdout.strip().split('\n')
        js = next((i for i, l in enumerate(lines) if l.strip().startswith('[')), -1)
        if js == -1:
            return "Error: Invalid output format"
        devices = json.loads('\n'.join(lines[js:]))
        if not devices:
            return "👥 <b>Online Users</b>\n\nTidak ada perangkat online"
        status_emoji = {"TERHUBUNG":"🟢","TERHUBUNG TIDAK AKTIF":"🟡","TIDAK DIKETAHUI":"🟠","TIDAK TERHUBUNG":"🔴"}
        out = "👥 <b>Online Users</b>\n\n"
        for idx, d in enumerate(devices, 1):
            emoji = status_emoji.get(d['status'], '⚪')
            hostname = d['hostname'] if d['hostname'] != '*' else 'Unknown'
            out += f"{idx}. {emoji} <b>{hostname}</b>\nIP: <code>{d['ip']}</code>\nMAC: <code>{d['mac']}</code>\nStatus: {d['status']}\n\n"
        return out
    except Exception as e:
        return f"Error: {str(e)}"

def format_bytes(b):
    if b < 1024: return f"{b} B"
    elif b < 1024**2: return f"{b/1024:.2f} KB"
    elif b < 1024**3: return f"{b/1024**2:.2f} MB"
    else: return f"{b/1024**3:.2f} GB"

def get_vnstat_traffic() -> str:
    try:
        out = "📊 <b>Traffic Statistics (eth1)</b>\n\n"
        try:
            r = subprocess.run(["sh", "/www/cgi-bin/traffic"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                lines = r.stdout.strip().split('\n')
                js = next((i for i, l in enumerate(lines) if l.strip().startswith('{')), -1)
                if js != -1:
                    d = json.loads('\n'.join(lines[js:]))
                    if "error" not in d:
                        out += f"📡 <b>Live:</b>\n⬇️ RX: <code>{format_bytes(int(d.get('rx',0)))}</code>\n⬆️ TX: <code>{format_bytes(int(d.get('tx',0)))}</code>\n\n"
        except: pass
        try:
            d = json.loads(run_command("vnstat --json d -i eth1"))
            if d and 'interfaces' in d:
                days = d['interfaces'][0]['traffic']['day']
                if days:
                    ld = days[-1]
                    out += f"📅 <b>Hari ini:</b>\n⬇️ {format_bytes(ld['rx'])}\n⬆️ {format_bytes(ld['tx'])}\n📊 Total: {format_bytes(ld['rx']+ld['tx'])}\n\n"
        except: pass
        try:
            d = json.loads(run_command("vnstat --json m -i eth1"))
            if d and 'interfaces' in d:
                months = d['interfaces'][0]['traffic']['month']
                if months:
                    lm = months[-1]
                    out += f"📈 <b>Bulan ini:</b>\n⬇️ {format_bytes(lm['rx'])}\n⬆️ {format_bytes(lm['tx'])}\n📊 Total: {format_bytes(lm['rx']+lm['tx'])}\n\n"
        except: pass
        return out.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def get_my_ip() -> str:
    try:
        for svc in ["https://api.ipify.org","https://ifconfig.me","https://icanhazip.com"]:
            try:
                ip = requests.get(svc, timeout=5).text.strip()
                try:
                    info = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5).json()
                    return (f"🌍 <b>Public IP Information</b>\n\nIP: <code>{ip}</code>\n"
                            f"ISP: <code>{info.get('org','N/A')}</code>\n"
                            f"Location: <code>{info.get('city','N/A')}, {info.get('region','N/A')}</code>\n"
                            f"Country: <code>{info.get('country','N/A')}</code>")
                except:
                    return f"🌍 <b>Public IP:</b> <code>{ip}</code>"
            except: continue
        return "Error: Unable to get public IP"
    except Exception as e:
        return f"Error: {str(e)}"

def ping_test(host: str = "8.8.8.8") -> str:
    try:
        result = run_command(f"ping -c 4 {host}")
        stats = [l for l in result.split('\n') if 'min/avg/max' in l or 'packet loss' in l]
        return f"🔍 <b>Ping Test ({host})</b>\n\n<code>{chr(10).join(stats)}</code>"
    except Exception as e:
        return f"Error: {str(e)}"

def speedtest() -> str:
    try:
        for binary in ["/usr/bin/speedtest-ookla", "/usr/bin/speedtest"]:
            if run_command(f"test -f {binary} && echo OK"):
                result = run_command(f"timeout 60 {binary} --accept-license --accept-gdpr 2>&1")
                lines = result.split('\n')
                data = {}
                for line in lines:
                    for k in ["Server","Latency","Download","Upload","Ping"]:
                        if f"{k}:" in line:
                            data[k] = line.split(f"{k}:")[1].strip()
                out = "⚡ <b>Speedtest Results</b>\n\n"
                for k,v in data.items():
                    out += f"{'📶' if k in ['Ping','Latency'] else '⬇️' if k=='Download' else '⬆️' if k=='Upload' else '🌐'} {k}: <code>{v}</code>\n"
                return out if data else f"<code>{result[:500]}</code>"
        if run_command("which speedtest-cli 2>/dev/null"):
            result = run_command("timeout 60 speedtest-cli --simple 2>&1")
            return f"⚡ <b>Speedtest</b>\n\n<code>{result}</code>"
        return "⚠️ <b>Speedtest tidak terinstall</b>\n\nInstall: <code>pip3 install speedtest-cli</code>"
    except Exception as e:
        return f"Error: {str(e)}"

def get_disk_info() -> str:
    try:
        out = "💿 <b>Disk Usage</b>\n\n"
        df = run_command("df -h")
        found = False
        for line in df.split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 6:
                fs, size, used, avail, pct, mount = parts[0],parts[1],parts[2],parts[3],parts[4],parts[5]
                if any(x in fs for x in ['sda','sdb','mmcblk','nvme']) or mount in ['/','/overlay','/opt']:
                    out += f"<b>{mount}</b> ({fs})\nSize: <code>{size}</code> | Used: <code>{used}</code> | Free: <code>{avail}</code> | <code>{pct}</code>\n\n"
                    found = True
        return out.strip() if found else out + "No disk found"
    except Exception as e:
        return f"Error: {str(e)}"

def leak_test() -> str:
    try:
        out = "🔒 <b>Leak Test</b>\n\n"
        try:
            ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
            out += f"🌍 <b>Public IP:</b> <code>{ip}</code>\n\n"
        except:
            out += "🌍 <b>Public IP:</b> Unable to fetch\n\n"
        out += "🔍 <b>DNS Servers:</b>\n"
        dns = run_command("cat /etc/resolv.conf | grep nameserver | awk '{print $2}'")
        for d in dns.split('\n')[:5]:
            if d.strip():
                out += f"  • <code>{d.strip()}</code>\n"
        return out
    except Exception as e:
        return f"Error: {str(e)}"

def adblock_test() -> str:
    try:
        test_domains = ["ads.google.com","doubleclick.net","googleadservices.com","googlesyndication.com","pagead2.googlesyndication.com"]
        out = "🛡 <b>AdBlock Test</b>\n\n"
        blocked = 0
        for domain in test_domains:
            r = run_command(f"nslookup {domain} 2>/dev/null")
            is_blocked = "NXDOMAIN" in r or "0.0.0.0" in r or "127.0.0.1" in r or not r.strip()
            out += ("✅" if is_blocked else "❌") + f" <code>{domain}</code>\n"
            if is_blocked: blocked += 1
        pct = blocked / len(test_domains) * 100
        out += f"\n📊 Blocked: {blocked}/{len(test_domains)} ({pct:.0f}%)"
        out += f"\n{'✅ EXCELLENT' if pct>=80 else '⚠️ PARTIAL' if pct>=40 else '❌ NOT WORKING'}"
        return out
    except Exception as e:
        return f"Error: {str(e)}"

def check_services() -> str:
    services = ["openclash", "nikki", "cloudflared"]
    out = "⚙️ <b>Services Status</b>\n\n"
    for svc in services:
        status = run_command(f"service {svc} status 2>&1")
        sl = status.lower()
        if "running" in sl or "active" in sl:
            out += f"✅ <b>{svc}:</b> RUNNING\n"
        elif "not found" in sl or "usage" in sl:
            out += f"❓ <b>{svc}:</b> NOT INSTALLED\n"
        else:
            ps = run_command(f"ps | grep {svc} | grep -v grep")
            out += (f"✅ <b>{svc}:</b> RUNNING\n" if ps else f"❌ <b>{svc}:</b> STOPPED\n")
    out += "\n💡 <i>Klik 'Service Control' untuk manage services</i>"
    return out

def service_control(service_name: str, action: str) -> str:
    try:
        if action not in ["start","stop","restart"]:
            return "❌ Invalid action"
        result = run_command(f"service {service_name} {action} 2>&1")
        import time; time.sleep(2)
        status = run_command(f"service {service_name} status 2>&1")
        return (f"⚙️ <b>Service Control</b>\n\nService: <code>{service_name}</code>\nAction: <code>{action}</code>\n\n"
                f"<b>Result:</b>\n<code>{result}</code>\n\n<b>Status:</b>\n<code>{status}</code>")
    except Exception as e:
        return f"Error: {str(e)}"

def get_container_info() -> str:
    try:
        out = "🐳 <b>Container Information</b>\n\n"
        tool = run_command("which docker 2>/dev/null") or run_command("which podman 2>/dev/null")
        if not tool:
            return out + "❌ Docker/Podman tidak terinstall"
        name = "docker" if "docker" in tool else "podman"
        containers = run_command(f"{name} ps -a --format '{{{{.Names}}}}|{{{{.Status}}}}|{{{{.Image}}}}'")
        if containers and "Error" not in containers:
            for line in containers.split('\n'):
                parts = line.split('|')
                if len(parts) >= 3:
                    icon = "🟢" if "Up" in parts[1] else "🔴"
                    out += f"{icon} <b>{parts[0]}</b>\n<code>{parts[2]}</code>\n{parts[1]}\n\n"
        else:
            out += "Tidak ada container"
        return out
    except Exception as e:
        return f"Error: {str(e)}"

# ==================== KEYBOARD ====================

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖥 CPU & RAM", callback_data="cpu_ram"),
         InlineKeyboardButton("👥 Online Users", callback_data="online_users")],
        [InlineKeyboardButton("📊 Traffic", callback_data="traffic"),
         InlineKeyboardButton("🌍 My IP", callback_data="myip")],
        [InlineKeyboardButton("🔍 Ping", callback_data="ping"),
         InlineKeyboardButton("⚡ Speedtest", callback_data="speedtest")],
        [InlineKeyboardButton("💿 Disk", callback_data="disk"),
         InlineKeyboardButton("🔒 Leak Test", callback_data="leaktest")],
        [InlineKeyboardButton("🛡 AdBlock", callback_data="adblock"),
         InlineKeyboardButton("⚙️ Services", callback_data="services")],
        [InlineKeyboardButton("🐳 Containers", callback_data="containers"),
         InlineKeyboardButton("💻 Command", callback_data="command")],
    ])

def get_reply_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📋 Menu"), KeyboardButton("ℹ️ Help"), KeyboardButton("🔄 Refresh")]], resize_keyboard=True)

def get_services_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Service Control", callback_data="service_control")],
                                  [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]])

def get_service_control_keyboard():
    services = ["openclash","nikki","cloudflared"]
    kb = []
    for s in services:
        kb.append([InlineKeyboardButton("▶️ Start", callback_data=f"svc_start_{s}"),
                   InlineKeyboardButton(s, callback_data=f"svc_info_{s}"),
                   InlineKeyboardButton("⏹ Stop", callback_data=f"svc_stop_{s}")])
        kb.append([InlineKeyboardButton(f"🔄 Restart {s}", callback_data=f"svc_restart_{s}")])
    kb.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(kb)

def get_containers_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]])

# ==================== HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        await update.message.reply_text(f"❌ Unauthorized!\nUser ID: <code>{update.effective_user.id}</code>", parse_mode='HTML')
        return
    await update.message.reply_text(
        f"🤖 <b>RemotWRT Bot</b>\n\nSelamat datang! Pilih menu:",
        reply_markup=get_main_keyboard(), parse_mode='HTML')
    await update.message.reply_text("Navigasi cepat:", reply_markup=get_reply_keyboard())

async def handle_keyboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id): return
    text = update.message.text
    if text in ["📋 Menu", "🔄 Refresh"]:
        await update.message.reply_text("📋 <b>MENU UTAMA</b>", parse_mode='HTML', reply_markup=get_main_keyboard())
    elif text == "ℹ️ Help":
        help_text = ("🤖 <b>PANDUAN BOT</b>\n\n"
                     "• 🖥 CPU & RAM — Info CPU dan memory\n• 👥 Online Users — Device online\n"
                     "• 📊 Traffic — Statistik bandwidth\n• 🌍 My IP — Info IP public\n"
                     "• 🔍 Ping — Test koneksi\n• ⚡ Speedtest — Test kecepatan\n"
                     "• 💿 Disk — Info storage\n• 🔒 Leak Test — DNS/IP leak\n"
                     "• 🛡 AdBlock — Test adblock\n• ⚙️ Services — Status services\n"
                     "• 🐳 Containers — Docker/Podman\n• 💻 Command — Shell command\n\n"
                     "<b>Custom command:</b>\n<code>/cmd uptime</code>")
        await update.message.reply_text(help_text, parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not check_auth(query.from_user.id):
        await query.answer("❌ Unauthorized!"); return
    await query.answer()
    cb = query.data

    if cb == "back_to_menu":
        await query.edit_message_text("📋 <b>MENU UTAMA</b>\n\nPilih menu:", parse_mode='HTML', reply_markup=get_main_keyboard())
        return

    if cb.startswith("svc_"):
        parts = cb.split("_", 2)
        if len(parts) == 3:
            action, service = parts[1], parts[2]
            if action == "info":
                status = run_command(f"service {service} status 2>&1")
                await query.edit_message_text(f"⚙️ <b>Service Info</b>\n\n<code>{service}</code>\n\n<code>{status}</code>",
                                              parse_mode='HTML', reply_markup=get_service_control_keyboard())
            else:
                loading = await query.edit_message_text("⏳ Processing...")
                result = service_control(service, action)
                await loading.edit_text(result, parse_mode='HTML', reply_markup=get_service_control_keyboard())
        return

    if cb == "service_control":
        await query.edit_message_text("🔧 <b>SERVICE CONTROL</b>\n\nPilih service:", parse_mode='HTML', reply_markup=get_service_control_keyboard())
        return

    loading = await query.edit_message_text("⏳ Loading...")
    handlers = {
        "cpu_ram":      (get_cpu_ram_info,   get_main_keyboard),
        "online_users": (get_online_users,   get_main_keyboard),
        "traffic":      (get_vnstat_traffic, get_main_keyboard),
        "myip":         (get_my_ip,          get_main_keyboard),
        "ping":         (ping_test,          get_main_keyboard),
        "speedtest":    (speedtest,          get_main_keyboard),
        "disk":         (get_disk_info,      get_main_keyboard),
        "leaktest":     (leak_test,          get_main_keyboard),
        "adblock":      (adblock_test,       get_main_keyboard),
        "services":     (check_services,     get_services_keyboard),
        "containers":   (get_container_info, get_containers_keyboard),
    }
    if cb in handlers:
        fn, kb_fn = handlers[cb]
        try:
            result = fn()
            keyboard = kb_fn()
            if len(result) > 4000:
                chunks = [result[i:i+4000] for i in range(0, len(result), 4000)]
                await loading.edit_text(chunks[0], parse_mode='HTML', reply_markup=keyboard)
                for chunk in chunks[1:]:
                    await query.message.reply_text(chunk, parse_mode='HTML')
            else:
                await loading.edit_text(result, parse_mode='HTML', reply_markup=keyboard)
        except Exception as e:
            await loading.edit_text(f"❌ Error: {str(e)}", parse_mode='HTML', reply_markup=get_main_keyboard())
    elif cb == "command":
        await loading.edit_text("💻 <b>Command Mode</b>\n\nFormat: <code>/cmd your_command</code>\nContoh: <code>/cmd uptime</code>",
                                parse_mode='HTML', reply_markup=get_main_keyboard())

async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized!"); return
    if not context.args:
        await update.message.reply_text("❌ Format: <code>/cmd your_command</code>", parse_mode='HTML'); return
    command = ' '.join(context.args)
    blacklist = ['rm -rf', 'dd if=', 'mkfs', 'format', '> /dev/']
    if any(cmd in command.lower() for cmd in blacklist):
        await update.message.reply_text("❌ Dangerous command blocked!"); return
    loading = await update.message.reply_text("⏳ Executing...")
    result = run_command(command)
    if len(result) > 4000:
        result = result[:4000] + "\n... (truncated)"
    await loading.edit_text(f"💻 <b>Command:</b> <code>{command}</code>\n\n<b>Output:</b>\n<code>{result}</code>", parse_mode='HTML')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# ==================== MAIN ====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cmd", cmd_handler))
    app.add_handler(MessageHandler(filters.Regex('^(📋 Menu|ℹ️ Help|🔄 Refresh)$'), handle_keyboard_button))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    logger.info("RemotWRT Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
