#!/usr/bin/env python3
"""
OpenWRT Telegram Monitoring Bot untuk Raspberry Pi 4
Config dibaca dari UCI: /etc/config/remotbot

Setup:
  uci set remotbot.main.bot_token='TOKEN'
  uci set remotbot.main.allowed_users='USER_ID'
  uci set remotbot.main.enabled='1'
  uci commit remotbot
  /etc/init.d/remotbot start

Fitur:
  - Monitoring CPU, RAM, Disk, Traffic, IP, Ping, Speedtest
  - Notifikasi otomatis: CPU panas, RAM penuh, WAN putus/nyambung
  - Alert WAN jika putus lebih dari batas waktu (default 60 menit)
  - Blokir device tidak terdaftar (MAC whitelist via UCI)
  - Multi-bahasa ID/EN toggle
  - Service control (start/stop/restart)
"""

import asyncio
import logging
import subprocess
import json
import time
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==================== UCI CONFIG ====================

def uci_get(key: str, default: str = "") -> str:
    try:
        r = subprocess.run(["uci", "get", key], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return default

def uci_set(key: str, value: str) -> bool:
    try:
        r = subprocess.run(["uci", "set", f"{key}={value}"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            subprocess.run(["uci", "commit", "remotbot"], timeout=5)
            return True
    except Exception:
        pass
    return False

def load_config() -> dict:
    allowed_str = uci_get("remotbot.main.allowed_users", "")
    allowed_users = []
    for uid in allowed_str.replace(",", " ").split():
        uid = uid.strip()
        if uid.lstrip("-").isdigit():
            allowed_users.append(int(uid))

    mac_str = uci_get("remotbot.main.mac_whitelist", "")
    mac_whitelist = [m.strip().lower() for m in mac_str.replace(",", " ").split() if m.strip()]

    return {
        "bot_token":             uci_get("remotbot.main.bot_token", ""),
        "allowed_users":         allowed_users,
        "cgi_online_path":       uci_get("remotbot.main.cgi_online_path", "/www/cgi-bin/online"),
        "language":              uci_get("remotbot.main.language", "id"),
        "cpu_temp_threshold":    int(uci_get("remotbot.main.cpu_temp_threshold", "75")),
        "ram_threshold":         int(uci_get("remotbot.main.ram_threshold", "85")),
        "wan_timeout_minutes":   int(uci_get("remotbot.main.wan_timeout_minutes", "60")),
        "mac_whitelist":         mac_whitelist,
        "notify_cpu_temp":       uci_get("remotbot.main.notify_cpu_temp", "1") == "1",
        "notify_ram":            uci_get("remotbot.main.notify_ram", "1") == "1",
        "notify_wan":            uci_get("remotbot.main.notify_wan", "1") == "1",
        "notify_unknown_device": uci_get("remotbot.main.notify_unknown_device", "1") == "1",
    }

def save_config_uci(key: str, value) -> bool:
    return uci_set(f"remotbot.main.{key}", str(value))

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== VALIDASI TOKEN ====================
_init_cfg = load_config()
BOT_TOKEN = _init_cfg.get("bot_token", "")

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

# ==================== I18N ====================
STRINGS = {
    "id": {
        "unauthorized":    "❌ Akses tidak diizinkan!\nUser ID kamu: <code>{uid}</code>",
        "welcome":         "🤖 <b>RemotWRT Bot</b>\n\nSelamat datang! Pilih menu di bawah:",
        "nav_hint":        "Gunakan tombol di bawah untuk navigasi cepat:",
        "menu":            "📋 <b>MENU UTAMA</b>\n\nPilih menu yang Anda inginkan:",
        "refreshed":       "🔄 <b>Refreshed!</b>\n\nData terbaru tersedia.",
        "help":            ("🤖 <b>PANDUAN BOT</b>\n\n"
                            "• 🖥 CPU & RAM — Info CPU dan memory\n"
                            "• 👥 Online Users — Device online di jaringan\n"
                            "• 📊 Traffic — Statistik bandwidth\n"
                            "• 🌍 My IP — Info IP publik\n"
                            "• 🔍 Ping — Test koneksi\n"
                            "• ⚡ Speedtest — Test kecepatan internet\n"
                            "• 💿 Disk — Info storage\n"
                            "• 🔒 Leak Test — DNS/IP leak\n"
                            "• 🛡 AdBlock — Test adblock\n"
                            "• ⚙️ Services — Status services\n"
                            "• 🐳 Containers — Docker/Podman\n"
                            "• 🚫 Blokir Device — Manajemen MAC blokir\n"
                            "• ⚙️ Settings — Bahasa & notifikasi\n\n"
                            "<b>NOTIFIKASI OTOMATIS:</b>\n"
                            "• 🌡 CPU panas | 💾 RAM penuh\n"
                            "• 📡 WAN putus/nyambung\n"
                            "• ⚠️ Device tak dikenal di jaringan\n\n"
                            "<b>Custom command:</b>\n<code>/cmd uptime</code>"),
        "cmd_format":      "❌ Format: <code>/cmd perintah_anda</code>",
        "cmd_blocked":     "❌ Perintah berbahaya diblokir!",
        "executing":       "⏳ Menjalankan...",
        "loading":         "⏳ Memuat...",
        "processing":      "⏳ Memproses...",
        "error":           "❌ Terjadi kesalahan",
        "back_menu":       "🔙 Kembali ke Menu",
        "service_ctrl":    "🔧 Kontrol Service",
        "wan_down":        "🚨 <b>ALERT: WAN Terputus!</b>\n\nWaktu: <code>{time}</code>",
        "wan_up":          "✅ <b>WAN Pulih!</b>\n\nDowntime: <code>{duration}</code>\nWaktu: <code>{time}</code>",
        "wan_long_down":   "⚠️ <b>WAN masih putus selama {duration}!</b>\n\nSegera periksa koneksi internet.",
        "cpu_alert":       "🌡 <b>ALERT: Suhu CPU Tinggi!</b>\n\nSuhu: <code>{temp}°C</code> (batas: {threshold}°C)\nWaktu: <code>{time}</code>",
        "ram_alert":       "💾 <b>ALERT: RAM Hampir Penuh!</b>\n\nPenggunaan: <code>{usage}%</code> (batas: {threshold}%)\nWaktu: <code>{time}</code>",
        "unknown_device":  "⚠️ <b>Perangkat Tak Dikenal!</b>\n\nMAC: <code>{mac}</code>\nIP: <code>{ip}</code>\nHostname: <code>{hostname}</code>\nWaktu: <code>{time}</code>\n\nIngin memblokir perangkat ini?",
        "device_blocked":  "🚫 <b>Perangkat Diblokir</b>\n\nMAC: <code>{mac}</code>\nIP: <code>{ip}</code>",
        "device_allowed":  "✅ <b>Perangkat Diizinkan & Ditambah ke Whitelist</b>\n\nMAC: <code>{mac}</code>",
        "block_title":     "🚫 <b>Manajemen Blokir Device</b>",
        "no_blocked":      "Tidak ada perangkat yang diblokir saat ini.",
        "whitelist_empty": "⚠️ Whitelist MAC kosong.\nFitur blokir device tak dikenal tidak aktif.\n\nTambah MAC:\n<code>uci add_list remotbot.main.mac_whitelist='aa:bb:cc:dd:ee:ff'</code>\n<code>uci commit remotbot</code>",
        "settings_title":  "⚙️ <b>Pengaturan Bot</b>",
    },
    "en": {
        "unauthorized":    "❌ Unauthorized access!\nYour User ID: <code>{uid}</code>",
        "welcome":         "🤖 <b>RemotWRT Bot</b>\n\nWelcome! Choose menu below:",
        "nav_hint":        "Use buttons below for quick navigation:",
        "menu":            "📋 <b>MAIN MENU</b>\n\nChoose an option:",
        "refreshed":       "🔄 <b>Refreshed!</b>\n\nLatest data available.",
        "help":            ("🤖 <b>BOT GUIDE</b>\n\n"
                            "• 🖥 CPU & RAM — CPU and memory info\n"
                            "• 👥 Online Users — Connected devices\n"
                            "• 📊 Traffic — Bandwidth statistics\n"
                            "• 🌍 My IP — Public IP info\n"
                            "• 🔍 Ping — Connection test\n"
                            "• ⚡ Speedtest — Internet speed test\n"
                            "• 💿 Disk — Storage info\n"
                            "• 🔒 Leak Test — DNS/IP leak\n"
                            "• 🛡 AdBlock — AdBlock test\n"
                            "• ⚙️ Services — Service status\n"
                            "• 🐳 Containers — Docker/Podman\n"
                            "• 🚫 Block Device — MAC block management\n"
                            "• ⚙️ Settings — Language & notifications\n\n"
                            "<b>AUTO NOTIFICATIONS:</b>\n"
                            "• 🌡 CPU hot | 💾 RAM full\n"
                            "• 📡 WAN down/up\n"
                            "• ⚠️ Unknown device on network\n\n"
                            "<b>Custom command:</b>\n<code>/cmd uptime</code>"),
        "cmd_format":      "❌ Format: <code>/cmd your_command</code>",
        "cmd_blocked":     "❌ Dangerous command blocked!",
        "executing":       "⏳ Executing...",
        "loading":         "⏳ Loading...",
        "processing":      "⏳ Processing...",
        "error":           "❌ An error occurred",
        "back_menu":       "🔙 Back to Menu",
        "service_ctrl":    "🔧 Service Control",
        "wan_down":        "🚨 <b>ALERT: WAN Down!</b>\n\nTime: <code>{time}</code>",
        "wan_up":          "✅ <b>WAN Restored!</b>\n\nDowntime: <code>{duration}</code>\nTime: <code>{time}</code>",
        "wan_long_down":   "⚠️ <b>WAN still down for {duration}!</b>\n\nPlease check your internet connection.",
        "cpu_alert":       "🌡 <b>ALERT: CPU Temperature High!</b>\n\nTemp: <code>{temp}°C</code> (limit: {threshold}°C)\nTime: <code>{time}</code>",
        "ram_alert":       "💾 <b>ALERT: RAM Almost Full!</b>\n\nUsage: <code>{usage}%</code> (limit: {threshold}%)\nTime: <code>{time}</code>",
        "unknown_device":  "⚠️ <b>Unknown Device Detected!</b>\n\nMAC: <code>{mac}</code>\nIP: <code>{ip}</code>\nHostname: <code>{hostname}</code>\nTime: <code>{time}</code>\n\nDo you want to block this device?",
        "device_blocked":  "🚫 <b>Device Blocked</b>\n\nMAC: <code>{mac}</code>\nIP: <code>{ip}</code>",
        "device_allowed":  "✅ <b>Device Allowed & Added to Whitelist</b>\n\nMAC: <code>{mac}</code>",
        "block_title":     "🚫 <b>Device Block Management</b>",
        "no_blocked":      "No blocked devices currently.",
        "whitelist_empty": "⚠️ MAC whitelist is empty.\nAdd MAC via:\n<code>uci add_list remotbot.main.mac_whitelist='aa:bb:cc:dd:ee:ff'</code>\n<code>uci commit remotbot</code>",
        "settings_title":  "⚙️ <b>Bot Settings</b>",
    }
}

def t(key: str, cfg: dict = None, **kwargs) -> str:
    if cfg is None: cfg = load_config()
    lang = cfg.get("language", "id")
    s = STRINGS.get(lang, STRINGS["id"]).get(key, STRINGS["id"].get(key, key))
    if kwargs:
        try: s = s.format(**kwargs)
        except Exception: pass
    return s

# ==================== MONITOR STATE ====================
monitor_state = {
    "wan_down_since":      None,
    "wan_alert_sent":      False,
    "wan_long_alert_sent": False,
    "last_cpu_alert":      0,
    "last_ram_alert":      0,
    "alerted_macs":        set(),
}

# ==================== UTILS ====================

def check_auth(user_id: int) -> bool:
    return user_id in load_config().get("allowed_users", [])

def run_command(command: str, timeout: int = 30) -> str:
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else f"Error: {r.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Error: Command timeout"
    except Exception as e:
        return f"Error: {str(e)}"

def get_online_with_actions() -> str:
    """Tampilkan device online dengan tombol aksi blokir/whitelist"""
    devices = get_current_devices()
    if not devices:
        return "👥 <b>Online Users</b>\n\nTidak ada perangkat online"
    em = {"TERHUBUNG":"🟢","TERHUBUNG TIDAK AKTIF":"🟡","TIDAK DIKETAHUI":"🟠","TIDAK TERHUBUNG":"🔴"}
    out = "👥 <b>Online Users</b>\n<i>Pilih device untuk blokir atau tambah whitelist:</i>\n\n"
    for i, d in enumerate(devices, 1):
        hn = d.get("hostname","*") if d.get("hostname","*") != "*" else "Unknown"
        out += (f"{i}. {em.get(d.get('status',''),'⚪')} <b>{hn}</b>\n"
                f"   IP: <code>{d.get('ip','')}</code>\n"
                f"   MAC: <code>{d.get('mac','')}</code>\n\n")
    return out

def get_online_actions_keyboard() -> InlineKeyboardMarkup:
    """Keyboard dengan tombol aksi per device"""
    cfg = load_config()
    devices = get_current_devices()
    wl = [m.lower() for m in cfg.get("mac_whitelist", [])]
    blocked = [m.lower() for m in get_blocked_macs()]
    kb = []
    for d in devices:
        mac = d.get("mac","").lower()
        ip  = d.get("ip","")
        hn  = d.get("hostname","Unknown")
        if hn == "*": hn = "Unknown"
        # Baris nama device
        kb.append([InlineKeyboardButton(
            f"{'✅' if mac in wl else '🚫' if mac in blocked else '❔'} {hn} ({ip})",
            callback_data=f"dev_detail_{mac}_{ip}"
        )])
        # Baris tombol aksi
        row = []
        if mac not in wl:
            row.append(InlineKeyboardButton("✅ Whitelist", callback_data=f"dev_whitelist_{mac}"))
        if mac not in blocked:
            row.append(InlineKeyboardButton("🚫 Blokir", callback_data=f"dev_block_{mac}_{ip}"))
        else:
            row.append(InlineKeyboardButton("🔓 Unblokir", callback_data=f"dev_unblock_{mac}"))
        if row:
            kb.append(row)
    kb.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="online_users_manage"),
        InlineKeyboardButton(t("back_menu"), callback_data="back_to_menu")
    ])
    return InlineKeyboardMarkup(kb)

def get_whitelist_status() -> str:
    """Tampilkan status whitelist dan cara mengaktifkan fitur"""
    cfg = load_config()
    wl = cfg.get("mac_whitelist", [])
    blocked = get_blocked_macs()
    notify = cfg.get("notify_unknown_device", True)

    out = "🛡 <b>Manajemen Device</b>\n\n"

    # Status fitur
    if not notify:
        out += "⚠️ <b>Fitur deteksi device asing: NONAKTIF</b>\n"
        out += "Aktifkan di Settings atau ketuk tombol di bawah\n\n"
    elif not wl:
        out += "⚠️ <b>Whitelist kosong — fitur belum aktif!</b>\n"
        out += "Tambahkan device tepercaya ke whitelist\n"
        out += "supaya device asing bisa terdeteksi.\n\n"
    else:
        out += "✅ <b>Fitur deteksi device asing: AKTIF</b>\n\n"

    out += f"📋 <b>Whitelist:</b> <code>{len(wl)}</code> MAC\n"
    if wl:
        for mac in wl[:10]:
            out += f"  ✅ <code>{mac}</code>\n"
        if len(wl) > 10:
            out += f"  ... dan {len(wl)-10} lainnya\n"

    out += f"\n🚫 <b>Diblokir:</b> <code>{len(blocked)}</code> MAC\n"
    if blocked:
        for mac in blocked[:5]:
            out += f"  🔴 <code>{mac}</code>\n"

    out += ("\n💡 <b>Cara pakai:</b>\n"
            "1. Buka <b>Device Online</b> → pilih device tepercaya → <b>✅ Whitelist</b>\n"
            "2. Semua device baru yang tidak ada di whitelist akan dikirim alert\n"
            "3. Dari alert bisa langsung blokir atau izinkan\n")
    return out

def get_device_manage_keyboard() -> InlineKeyboardMarkup:
    """Keyboard utama manajemen device"""
    cfg = load_config()
    notify = cfg.get("notify_unknown_device", True)
    wl     = cfg.get("mac_whitelist", [])
    blocked = get_blocked_macs()
    kb = [
        [InlineKeyboardButton("👥 Device Online (Pilih Aksi)", callback_data="online_users_manage")],
        [InlineKeyboardButton(
            f"{'🔔 Nonaktifkan' if notify else '🔕 Aktifkan'} Deteksi Asing",
            callback_data="toggle_notify_unknown_device"
        )],
    ]
    if wl:
        kb.append([InlineKeyboardButton(f"📋 Hapus dari Whitelist ({len(wl)})", callback_data="manage_whitelist_del")])
    if blocked:
        kb.append([InlineKeyboardButton(f"🔓 Pilih Unblokir ({len(blocked)})", callback_data="manage_unblock_select")])
    kb.append([InlineKeyboardButton(t("back_menu"), callback_data="back_to_menu")])
    return InlineKeyboardMarkup(kb)

def get_whitelist_del_keyboard() -> InlineKeyboardMarkup:
    """Pilih MAC yang akan dihapus dari whitelist"""
    cfg = load_config()
    wl  = cfg.get("mac_whitelist", [])
    kb  = []
    for mac in wl:
        kb.append([InlineKeyboardButton(f"🗑 Hapus: {mac}", callback_data=f"wl_del_{mac}")])
    kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="block_menu")])
    return InlineKeyboardMarkup(kb)

def get_unblock_select_keyboard() -> InlineKeyboardMarkup:
    """Pilih MAC yang akan di-unblokir"""
    blocked = get_blocked_macs()
    kb = []
    for mac in blocked:
        kb.append([InlineKeyboardButton(f"🔓 Unblokir: {mac}", callback_data=f"sel_unblock_{mac}")])
    kb.append([InlineKeyboardButton("🔙 Kembali", callback_data="block_menu")])
    return InlineKeyboardMarkup(kb)


def format_bytes(b: int) -> str:
    if b < 1024:       return f"{b} B"
    elif b < 1024**2:  return f"{b/1024:.2f} KB"
    elif b < 1024**3:  return f"{b/1024**2:.2f} MB"
    else:              return f"{b/1024**3:.2f} GB"

def format_duration(secs: float) -> str:
    s = int(secs)
    if s < 60:     return f"{s}s"
    elif s < 3600: return f"{s//60}m {s%60}s"
    else:          return f"{s//3600}j {(s%3600)//60}m"

# ==================== SYSTEM CHECKS ====================

def get_cpu_temp() -> float:
    try:
        raw = run_command("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
        if raw and raw.replace('-','').isdigit():
            return float(raw) / 1000
    except Exception: pass
    return 0.0

def get_ram_usage() -> int:
    try:
        mem = run_command("free | grep Mem").split()
        if len(mem) >= 3:
            return int(int(mem[2]) / int(mem[1]) * 100)
    except Exception: pass
    return 0

def check_wan() -> bool:
    for host in ["8.8.8.8", "1.1.1.1", "114.114.114.114"]:
        r = run_command(f"ping -c 1 -W 3 {host}", timeout=10)
        if "1 received" in r:
            return True
    return False

def get_current_devices() -> list:
    try:
        cfg      = load_config()
        cgi_path = cfg.get("cgi_online_path", "/www/cgi-bin/online")
        r = subprocess.run(["sh", cgi_path], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return []
        lines = r.stdout.split("\n")
        json_lines = []; collecting = False
        for line in lines:
            stripped = line.strip()
            if not collecting and (stripped.startswith("[") or stripped.startswith("{")):
                collecting = True
            if collecting:
                json_lines.append(line)
        if not json_lines: return []
        data = json.loads("\n".join(json_lines).strip())
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"get_current_devices error: {e}")
        return []

def block_mac(mac: str) -> bool:
    """Blokir MAC — simpan ke UCI (persistent) + iptables (aktif sekarang)"""
    mac = mac.lower().strip()
    # 1. Simpan ke UCI remotbot.blocked_macs (persistent)
    run_command(f"uci add_list remotbot.main.blocked_macs=\'{mac}\'")
    run_command("uci commit remotbot")
    # 2. Blokir via iptables sekarang
    run_command(f"iptables -I FORWARD -m mac --mac-source {mac} -j DROP 2>/dev/null")
    # 3. Blokir via firewall OpenWrt (persistent reboot)
    name = "Block_" + mac.replace(":","")
    run_command(
        f"uci batch << EOF\n"
        f"add firewall rule\n"
        f"set firewall.@rule[-1].name=\'{name}\'\n"
        f"set firewall.@rule[-1].src=\'lan\'\n"
        f"set firewall.@rule[-1].dest=\'wan\'\n"
        f"set firewall.@rule[-1].src_mac=\'{mac}\'\n"
        f"set firewall.@rule[-1].target=\'REJECT\'\n"
        f"commit firewall\n"
        f"EOF"
    )
    return True

def unblock_mac(mac: str) -> bool:
    """Hapus blokir MAC dari UCI + iptables"""
    mac = mac.lower().strip()
    # 1. Hapus dari UCI remotbot
    macs = get_blocked_macs()
    run_command("uci delete remotbot.main.blocked_macs 2>/dev/null")
    for m in macs:
        if m != mac:
            run_command(f"uci add_list remotbot.main.blocked_macs=\'{m}\'")
    run_command("uci commit remotbot")
    # 2. Hapus dari iptables
    run_command(f"iptables -D FORWARD -m mac --mac-source {mac} -j DROP 2>/dev/null")
    # 3. Hapus dari firewall UCI
    name = "Block_" + mac.replace(":","")
    run_command(
        f"idx=$(uci show firewall 2>/dev/null | grep \"{name}\" | head -1 | cut -d. -f1-2); "
        f"[ -n \"$idx\" ] && uci delete $idx && uci commit firewall 2>/dev/null || true"
    )
    return True

def get_blocked_macs() -> list:
    """Ambil daftar MAC yang diblokir dari UCI (persistent)"""
    raw = uci_get("remotbot.main.blocked_macs", "")
    if not raw:
        return []
    return [m.strip().lower() for m in raw.replace(",", " ").split() if m.strip()]

def add_to_whitelist(mac: str) -> bool:
    mac = mac.lower().strip()
    run_command(f"uci add_list remotbot.main.mac_whitelist='{mac}'")
    run_command("uci commit remotbot")
    return True

# ==================== MONITORING FUNCTIONS ====================

def get_cpu_ram_info() -> str:
    try:
        sysinfo = run_command("sysinfo.sh --plain 2>/dev/null")
        if sysinfo and "Error" not in sysinfo and "=== System Info ===" in sysinfo:
            lines = sysinfo.split("\n"); out = []; capture = False
            for line in lines:
                if "=== System Info ===" in line: capture = True
                if capture and "RAM Available:" in line: out.append(line); break
                if any(x in line for x in ["=== Disk Usage ===","=== Network Interfaces ==="]): break
                if capture: out.append(line)
            if out:
                r = "🖥 <b>CPU & RAM Status</b>\n\n" + "\n".join(out)
                for h in ["System Info","CPU Temperature","CPU Usage","Load Average","CPU Info","Memory (RAM)","Swap"]:
                    r = r.replace(f"=== {h} ===", f"<b>=== {h} ===</b>")
                return r

        temp = get_cpu_temp()
        loadavg = run_command("cat /proc/loadavg")
        load = loadavg.split()[:3] if loadavg and "Error" not in loadavg else ["N/A","N/A","N/A"]

        cpu_pct = "N/A"
        try:
            stat1 = open("/proc/stat").readline().split()
            import time as _t; _t.sleep(0.5)
            stat2 = open("/proc/stat").readline().split()
            idle1 = int(stat1[4]); total1 = sum(int(x) for x in stat1[1:])
            idle2 = int(stat2[4]); total2 = sum(int(x) for x in stat2[1:])
            dt = total2 - total1
            if dt > 0: cpu_pct = f"{100*(dt-(idle2-idle1))//dt}"
        except Exception:
            cpu_pct = run_command("top -bn1 2>/dev/null | grep -E '^CPU' | awk -F'[%a-z ]+' '{print $2}'") or "N/A"

        try:
            meminfo = {}
            for line in open("/proc/meminfo"):
                k, v = line.split(":")
                meminfo[k.strip()] = int(v.strip().split()[0])
            total_kb = meminfo.get("MemTotal", 0)
            avail_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            used_kb  = total_kb - avail_kb
            pct      = int(used_kb / total_kb * 100) if total_kb else 0
            total_mb = total_kb//1024; used_mb = used_kb//1024; avail_mb = avail_kb//1024
        except Exception:
            mem = run_command("free | grep Mem").split()
            if len(mem) >= 4:
                total_kb = int(mem[1]); used_kb = int(mem[2]); avail_kb = int(mem[3])
                pct = int(used_kb/total_kb*100) if total_kb else 0
                total_mb = total_kb//1024; used_mb = used_kb//1024; avail_mb = avail_kb//1024
            else:
                total_mb = used_mb = avail_mb = pct = 0

        uptime_raw = run_command("cat /proc/uptime")
        uptime_str = format_duration(int(float(uptime_raw.split()[0]))) if uptime_raw and "Error" not in uptime_raw else "N/A"

        return (f"🖥 <b>CPU & RAM Status</b>\n\n"
                f"🌡 Suhu CPU: <code>{temp:.1f}°C</code>\n"
                f"📊 CPU Usage: <code>{cpu_pct}%</code>\n"
                f"⚡ Load Average: <code>{' '.join(load)}</code>\n"
                f"⏱ Uptime: <code>{uptime_str}</code>\n\n"
                f"💾 RAM Used: <code>{pct}% ({used_mb} MB / {total_mb} MB)</code>\n"
                f"💾 RAM Free: <code>{avail_mb} MB</code>")
    except Exception as e:
        return f"Error get_cpu_ram_info: {str(e)}"

def get_online_users() -> str:
    try:
        devices = get_current_devices()
        if not devices:
            return "👥 <b>Online Users</b>\n\nTidak ada perangkat online"
        em = {"TERHUBUNG":"🟢","TERHUBUNG TIDAK AKTIF":"🟡","TIDAK DIKETAHUI":"🟠","TIDAK TERHUBUNG":"🔴"}
        out = "👥 <b>Online Users</b>\n\n"
        for i, d in enumerate(devices, 1):
            hn = d.get('hostname','*') if d.get('hostname','*') != '*' else 'Unknown'
            out += (f"{i}. {em.get(d.get('status',''),'⚪')} <b>{hn}</b>\n"
                    f"   IP: <code>{d.get('ip','')}</code>\n"
                    f"   MAC: <code>{d.get('mac','')}</code>\n"
                    f"   Status: {d.get('status','')}\n\n")
        return out
    except Exception as e:
        return f"Error: {str(e)}"

def get_vnstat_traffic() -> str:
    try:
        iface_raw = run_command("ip route show default 2>/dev/null | awk '/default/ {print $5}' | head -1")
        iface     = iface_raw.strip() if iface_raw and "Error" not in iface_raw else "eth1"
        out = f"📊 <b>Traffic Statistics</b>\nInterface: <code>{iface}</code>\n\n"

        if not run_command("which vnstat 2>/dev/null"):
            try:
                rx = tx = 0
                with open("/proc/net/dev") as f:
                    for line in f:
                        if iface in line:
                            p = line.split(); rx = int(p[1]); tx = int(p[9]); break
                out += f"📡 <b>Total sejak boot:</b>\n⬇️ RX: <code>{format_bytes(rx)}</code>\n⬆️ TX: <code>{format_bytes(tx)}</code>\n\n"
                out += "ℹ️ <i>Install vnstat untuk statistik harian/bulanan</i>"
            except Exception as e:
                out += f"Error: {e}"
            return out

        for period, flag, label in [('d','day','📅 <b>Hari ini:</b>'),('m','month','📈 <b>Bulan ini:</b>')]:
            try:
                raw  = run_command(f"vnstat --json {period} -i {iface} 2>/dev/null")
                if not raw or "Error" in raw:
                    raw = run_command(f"vnstat --json {period} 2>/dev/null")
                data = json.loads(raw)
                if data and "interfaces" in data:
                    items = data["interfaces"][0]["traffic"].get(flag, [])
                    if items:
                        last = items[-1]; rx, tx = last.get("rx",0), last.get("tx",0)
                        out += f"{label}\n⬇️ RX: <code>{format_bytes(rx)}</code>\n⬆️ TX: <code>{format_bytes(tx)}</code>\n📊 Total: <code>{format_bytes(rx+tx)}</code>\n\n"
            except Exception as e:
                logger.warning(f"vnstat {period} error: {e}")
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
                except: return f"🌍 <b>Public IP:</b> <code>{ip}</code>"
            except: continue
        return "Error: Unable to get public IP"
    except Exception as e:
        return f"Error: {str(e)}"

def ping_test(host: str = "8.8.8.8") -> str:
    result = run_command(f"ping -c 4 {host}")
    stats  = [l for l in result.split('\n') if 'min/avg/max' in l or 'packet loss' in l]
    return f"🔍 <b>Ping Test ({host})</b>\n\n<code>{chr(10).join(stats)}</code>"

def speedtest() -> str:
    try:
        for binary in ["/usr/bin/speedtest-ookla","/usr/bin/speedtest"]:
            if run_command(f"test -f {binary} && echo OK") == "OK":
                result = run_command(f"timeout 60 {binary} --accept-license --accept-gdpr 2>&1")
                if "timeout" in result.lower(): return "⚡ Speedtest timeout >60 detik"
                lines = result.split('\n'); data = {}
                for line in lines:
                    for k in ["Server","Latency","Idle Latency","Download","Upload"]:
                        if f"{k}:" in line: data[k] = line.split(f"{k}:")[1].strip()
                out = "⚡ <b>Speedtest Results</b>\n\n"
                for k, v in data.items():
                    icon = "🌐" if k=="Server" else "📶" if "Latency" in k else "⬇️" if k=="Download" else "⬆️"
                    out += f"{icon} {k}: <code>{v}</code>\n"
                return out if data else f"<code>{result[:500]}</code>"
        if run_command("which speedtest-cli 2>/dev/null"):
            return f"⚡ <b>Speedtest</b>\n\n<code>{run_command('timeout 60 speedtest-cli --simple 2>&1')}</code>"
        return "⚠️ Speedtest tidak terinstall.\nInstall: <code>pip3 install speedtest-cli</code>"
    except Exception as e:
        return f"Error: {str(e)}"

def get_disk_info() -> str:
    try:
        out = "💿 <b>Disk Usage</b>\n\n"; found = False
        for line in run_command("df -h").split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 6:
                fs,size,used,avail,pct,mount = parts[0],parts[1],parts[2],parts[3],parts[4],parts[5]
                if any(x in fs for x in ['sda','sdb','mmcblk','nvme']) or mount in ['/','/overlay','/opt']:
                    out += f"<b>{mount}</b> ({fs})\nSize: <code>{size}</code> | Used: <code>{used}</code> | Free: <code>{avail}</code> | <code>{pct}</code>\n\n"
                    found = True
        return out.strip() if found else out + "No disk found"
    except Exception as e:
        return f"Error: {str(e)}"

def leak_test() -> str:
    try:
        out = "🔒 <b>Leak Test</b>\n\n"
        try: out += f"🌍 <b>Public IP:</b> <code>{requests.get('https://api.ipify.org',timeout=5).text.strip()}</code>\n\n"
        except: out += "🌍 <b>Public IP:</b> Unable to fetch\n\n"
        out += "🔍 <b>DNS Servers:</b>\n"
        for d in run_command("cat /etc/resolv.conf | grep nameserver | awk '{print $2}'").split('\n')[:5]:
            if d.strip(): out += f"  • <code>{d.strip()}</code>\n"
        return out
    except Exception as e:
        return f"Error: {str(e)}"

def adblock_test() -> str:
    try:
        domains = [("ads.google.com","Google Ads"),("doubleclick.net","DoubleClick"),
                   ("googleadservices.com","Google Ad Services"),("googlesyndication.com","Google Syndication"),
                   ("pagead2.googlesyndication.com","Page Ads")]
        out = "🛡 <b>AdBlock Test</b>\n\n"; blocked = 0
        for domain, name in domains:
            r  = run_command(f"nslookup {domain} 2>/dev/null")
            ok = "NXDOMAIN" in r or "0.0.0.0" in r or "127.0.0.1" in r or not r.strip()
            out += f"{'✅' if ok else '❌'} {name}\n"
            if ok: blocked += 1
        pct = blocked / len(domains) * 100
        out += f"\n📊 Blocked: {blocked}/{len(domains)} ({pct:.0f}%)"
        out += f"\n{'✅ EXCELLENT' if pct>=80 else '⚠️ PARTIAL' if pct>=40 else '❌ NOT WORKING'}"
        return out
    except Exception as e:
        return f"Error: {str(e)}"

def check_services() -> str:
    services = ["openclash","nikki","cloudflared"]
    out = "⚙️ <b>Services Status</b>\n\n"
    for svc in services:
        st = run_command(f"service {svc} status 2>&1").lower()
        if "running" in st or "active" in st: out += f"✅ <b>{svc}:</b> RUNNING\n"
        elif "not found" in st or "usage" in st: out += f"❓ <b>{svc}:</b> NOT INSTALLED\n"
        else:
            ps = run_command(f"ps | grep {svc} | grep -v grep")
            out += f"{'✅' if ps else '❌'} <b>{svc}:</b> {'RUNNING' if ps else 'STOPPED'}\n"
    out += "\n💡 <i>Klik 'Service Control' untuk manage services</i>"
    return out

def service_control(service_name: str, action: str) -> str:
    if action not in ["start","stop","restart"]: return "❌ Invalid action"
    result = run_command(f"service {service_name} {action} 2>&1")
    time.sleep(2)
    status = run_command(f"service {service_name} status 2>&1")
    return (f"⚙️ <b>Service Control</b>\n\nService: <code>{service_name}</code>\nAction: <code>{action}</code>\n\n"
            f"<b>Result:</b>\n<code>{result}</code>\n\n<b>Status:</b>\n<code>{status}</code>")

def get_container_info() -> str:
    try:
        out  = "🐳 <b>Container Information</b>\n\n"
        tool = run_command("which docker 2>/dev/null") or run_command("which podman 2>/dev/null")
        if not tool: return out + "❌ Docker/Podman tidak terinstall"
        name = "docker" if "docker" in tool else "podman"
        containers = run_command(f"{name} ps -a --format '{{{{.Names}}}}|{{{{.Status}}}}|{{{{.Image}}}}'")
        if containers and "Error" not in containers:
            for line in containers.split('\n'):
                parts = line.split('|')
                if len(parts) >= 3:
                    out += f"{'🟢' if 'Up' in parts[1] else '🔴'} <b>{parts[0]}</b>\n   <code>{parts[2]}</code>\n   {parts[1]}\n\n"
        else: out += "Tidak ada container"
        return out
    except Exception as e:
        return f"Error: {str(e)}"

# ==================== SETTINGS UI ====================

def get_settings_text(cfg: dict) -> str:
    lang  = cfg.get("language","id"); flag = "🇮🇩" if lang=="id" else "🇬🇧"
    label = "Indonesia" if lang=="id" else "English"
    return (f"{t('settings_title',cfg)}\n\n{flag} Bahasa: <code>{label}</code>\n\n"
            f"<b>Notifikasi Otomatis:</b>\n"
            f"{'🔔' if cfg.get('notify_cpu_temp') else '🔕'} CPU Panas (batas: <code>{cfg.get('cpu_temp_threshold',75)}°C</code>)\n"
            f"{'🔔' if cfg.get('notify_ram') else '🔕'} RAM Penuh (batas: <code>{cfg.get('ram_threshold',85)}%</code>)\n"
            f"{'🔔' if cfg.get('notify_wan') else '🔕'} WAN Putus (alert > <code>{cfg.get('wan_timeout_minutes',60)} menit</code>)\n"
            f"{'🔔' if cfg.get('notify_unknown_device') else '🔕'} Device Tak Dikenal\n\n"
            f"<i>Ketuk tombol untuk toggle on/off</i>")

def get_block_menu_text(cfg: dict) -> str:
    blocked = get_blocked_macs(); wl = cfg.get("mac_whitelist",[])
    text = (f"{t('block_title',cfg)}\n\n📋 Whitelist: <code>{len(wl)}</code> MAC\n"
            f"🚫 Diblokir: <code>{len(blocked)}</code> MAC\n\n")
    if blocked:
        text += "<b>MAC Terblokir:</b>\n"
        for mac in blocked[:10]: text += f"  🔴 <code>{mac}</code>\n"
    else: text += t("no_blocked",cfg)
    if not wl: text += f"\n\n{t('whitelist_empty',cfg)}"
    return text

# ==================== KEYBOARDS ====================

def get_main_keyboard(cfg: dict = None) -> InlineKeyboardMarkup:
    if cfg is None: cfg = load_config()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖥 CPU & RAM",     callback_data="cpu_ram"),
         InlineKeyboardButton("👥 Online Users",  callback_data="online_users")],
        [InlineKeyboardButton("📊 Traffic",       callback_data="traffic"),
         InlineKeyboardButton("🌍 My IP",         callback_data="myip")],
        [InlineKeyboardButton("🔍 Ping",          callback_data="ping"),
         InlineKeyboardButton("⚡ Speedtest",     callback_data="speedtest")],
        [InlineKeyboardButton("💿 Disk",          callback_data="disk"),
         InlineKeyboardButton("🔒 Leak Test",     callback_data="leaktest")],
        [InlineKeyboardButton("🛡 AdBlock",       callback_data="adblock"),
         InlineKeyboardButton("⚙️ Services",      callback_data="services")],
        [InlineKeyboardButton("🐳 Containers",    callback_data="containers"),
         InlineKeyboardButton("💻 Command",       callback_data="command")],
        [InlineKeyboardButton("🛡 Kelola Device", callback_data="block_menu"),
         InlineKeyboardButton("⚙️ Settings",      callback_data="settings")],
    ])

def get_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton("📋 Menu"),KeyboardButton("ℹ️ Help"),KeyboardButton("🔄 Refresh")]], resize_keyboard=True)

def get_services_keyboard(cfg: dict = None) -> InlineKeyboardMarkup:
    if cfg is None: cfg = load_config()
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("service_ctrl",cfg),callback_data="service_control")],
                                  [InlineKeyboardButton(t("back_menu",cfg),callback_data="back_to_menu")]])

def get_service_control_keyboard(cfg: dict = None) -> InlineKeyboardMarkup:
    if cfg is None: cfg = load_config()
    kb = []
    for svc in ["openclash","nikki","cloudflared"]:
        kb.append([InlineKeyboardButton("▶️ Start",callback_data=f"svc_start_{svc}"),
                   InlineKeyboardButton(svc,callback_data=f"svc_info_{svc}"),
                   InlineKeyboardButton("⏹ Stop",callback_data=f"svc_stop_{svc}")])
        kb.append([InlineKeyboardButton(f"🔄 Restart {svc}",callback_data=f"svc_restart_{svc}")])
    kb.append([InlineKeyboardButton(t("back_menu",cfg),callback_data="back_to_menu")])
    return InlineKeyboardMarkup(kb)

def get_settings_keyboard(cfg: dict = None) -> InlineKeyboardMarkup:
    if cfg is None: cfg = load_config()
    lang = cfg.get("language","id")
    def nb(key, label):
        on = cfg.get(key,True)
        return InlineKeyboardButton(f"{'🔔' if on else '🔕'} {label}", callback_data=f"toggle_{key}")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🌐 Ganti ke {'EN 🇬🇧' if lang=='id' else 'ID 🇮🇩'}",callback_data="toggle_lang")],
        [nb("notify_cpu_temp","CPU Temp"), nb("notify_ram","RAM")],
        [nb("notify_wan","WAN Alert"),     nb("notify_unknown_device","Device Asing")],
        [InlineKeyboardButton(t("back_menu",cfg),callback_data="back_to_menu")]
    ])

def get_block_keyboard(cfg: dict = None) -> InlineKeyboardMarkup:
    if cfg is None: cfg = load_config()
    blocked = get_blocked_macs(); kb = []
    for mac in blocked[:5]:
        kb.append([InlineKeyboardButton(f"✅ Izinkan {mac}",callback_data=f"unblock_{mac}")])
    kb.append([InlineKeyboardButton("🔄 Refresh",callback_data="block_menu"),
               InlineKeyboardButton("📋 Whitelist",callback_data="show_whitelist")])
    kb.append([InlineKeyboardButton(t("back_menu",cfg),callback_data="back_to_menu")])
    return InlineKeyboardMarkup(kb)

# ==================== BACKGROUND MONITOR ====================

async def send_alert(app, message: str, keyboard=None):
    cfg = load_config()
    for uid in cfg.get("allowed_users",[]):
        try:
            kw = {"chat_id":uid,"text":message,"parse_mode":"HTML"}
            if keyboard: kw["reply_markup"] = keyboard
            await app.bot.send_message(**kw)
        except Exception as e:
            logger.error(f"Alert error to {uid}: {e}")

async def monitor_loop(app):
    global monitor_state
    logger.info("Background monitor started")
    await asyncio.sleep(30)
    while True:
        try:
            cfg = load_config(); now = datetime.now(); now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            if cfg.get("notify_wan",True):
                wan_ok = check_wan()
                if not wan_ok:
                    if monitor_state["wan_down_since"] is None:
                        monitor_state.update({"wan_down_since":now,"wan_alert_sent":False,"wan_long_alert_sent":False})
                    if not monitor_state["wan_alert_sent"]:
                        await send_alert(app, t("wan_down",cfg,time=now_str))
                        monitor_state["wan_alert_sent"] = True
                    dur = (now - monitor_state["wan_down_since"]).total_seconds()
                    if dur >= cfg.get("wan_timeout_minutes",60)*60 and not monitor_state["wan_long_alert_sent"]:
                        await send_alert(app, t("wan_long_down",cfg,duration=format_duration(dur)))
                        monitor_state["wan_long_alert_sent"] = True
                else:
                    if monitor_state["wan_down_since"] is not None:
                        dur = (now - monitor_state["wan_down_since"]).total_seconds()
                        await send_alert(app, t("wan_up",cfg,duration=format_duration(dur),time=now_str))
                    monitor_state.update({"wan_down_since":None,"wan_alert_sent":False,"wan_long_alert_sent":False})

            if cfg.get("notify_cpu_temp",True):
                temp = get_cpu_temp(); threshold = cfg.get("cpu_temp_threshold",75)
                if temp > threshold and (time.time()-monitor_state["last_cpu_alert"]) > 1800:
                    await send_alert(app, t("cpu_alert",cfg,temp=f"{temp:.1f}",threshold=threshold,time=now_str))
                    monitor_state["last_cpu_alert"] = time.time()

            if cfg.get("notify_ram",True):
                ram = get_ram_usage(); threshold = cfg.get("ram_threshold",85)
                if ram > threshold and (time.time()-monitor_state["last_ram_alert"]) > 1800:
                    await send_alert(app, t("ram_alert",cfg,usage=ram,threshold=threshold,time=now_str))
                    monitor_state["last_ram_alert"] = time.time()

            if cfg.get("notify_unknown_device",True):
                wl = [m.lower() for m in cfg.get("mac_whitelist",[])]
                if wl:
                    for dev in get_current_devices():
                        mac = dev.get("mac","").lower()
                        if not mac: continue
                        blocked = get_blocked_macs()
                        if mac not in wl and mac not in blocked and mac not in monitor_state["alerted_macs"]:
                            monitor_state["alerted_macs"].add(mac)
                            ip = dev.get("ip","?"); hn = dev.get("hostname","?")
                            kb = InlineKeyboardMarkup([[
                                InlineKeyboardButton("🚫 Blokir",  callback_data=f"quick_block_{mac}_{ip}"),
                                InlineKeyboardButton("✅ Izinkan", callback_data=f"quick_allow_{mac}"),
                            ]])
                            await send_alert(app, t("unknown_device",cfg,mac=mac,ip=ip,hostname=hn,time=now_str), keyboard=kb)
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        await asyncio.sleep(60)

# ==================== HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; cfg = load_config()
    if not check_auth(uid):
        await update.message.reply_text(t("unauthorized",cfg,uid=uid), parse_mode='HTML'); return
    await update.message.reply_text(t("welcome",cfg), reply_markup=get_main_keyboard(cfg), parse_mode='HTML')
    await update.message.reply_text(t("nav_hint",cfg), reply_markup=get_reply_keyboard())

async def handle_keyboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id): return
    cfg = load_config(); text = update.message.text
    if text in ["📋 Menu","🔄 Refresh"]:
        await update.message.reply_text(t("menu",cfg), parse_mode='HTML', reply_markup=get_main_keyboard(cfg))
    elif text == "ℹ️ Help":
        await update.message.reply_text(t("help",cfg), parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; uid = query.from_user.id
    if not check_auth(uid): await query.answer("❌ Unauthorized!"); return
    await query.answer(); cb = query.data; cfg = load_config()

    if cb == "back_to_menu":
        await query.edit_message_text(t("menu",cfg), parse_mode='HTML', reply_markup=get_main_keyboard(cfg)); return
    if cb == "settings":
        await query.edit_message_text(get_settings_text(cfg), parse_mode='HTML', reply_markup=get_settings_keyboard(cfg)); return
    if cb == "toggle_lang":
        save_config_uci("language","en" if cfg.get("language","id")=="id" else "id")
        cfg2 = load_config()
        await query.edit_message_text(get_settings_text(cfg2), parse_mode='HTML', reply_markup=get_settings_keyboard(cfg2)); return
    if cb.startswith("toggle_notify"):
        key = cb.replace("toggle_",""); save_config_uci(key,"0" if cfg.get(key,True) else "1")
        cfg2 = load_config()
        await query.edit_message_text(get_settings_text(cfg2), parse_mode='HTML', reply_markup=get_settings_keyboard(cfg2)); return
    if cb == "block_menu":
        await query.edit_message_text(get_whitelist_status(), parse_mode='HTML', reply_markup=get_device_manage_keyboard()); return

    if cb == "online_users_manage":
        await query.edit_message_text(get_online_with_actions(), parse_mode='HTML', reply_markup=get_online_actions_keyboard()); return

    if cb.startswith("dev_detail_"):
        # Abaikan — sudah ditampilkan di list
        return

    if cb.startswith("dev_whitelist_"):
        mac = cb[14:]
        add_to_whitelist(mac)
        monitor_state["alerted_macs"].discard(mac)
        cfg2 = load_config()
        await query.answer(f"✅ {mac} ditambah ke whitelist!")
        await query.edit_message_text(get_online_with_actions(), parse_mode='HTML', reply_markup=get_online_actions_keyboard()); return

    if cb.startswith("dev_block_"):
        parts = cb.split("_", 3)
        mac = parts[2]; ip = parts[3] if len(parts) > 3 else "?"
        block_mac(mac)
        monitor_state["alerted_macs"].discard(mac)
        await query.answer(f"🚫 {mac} diblokir!")
        await query.edit_message_text(get_online_with_actions(), parse_mode='HTML', reply_markup=get_online_actions_keyboard()); return

    if cb.startswith("dev_unblock_"):
        mac = cb[12:]
        unblock_mac(mac)
        await query.answer(f"🔓 {mac} di-unblokir!")
        await query.edit_message_text(get_online_with_actions(), parse_mode='HTML', reply_markup=get_online_actions_keyboard()); return

    if cb == "clear_whitelist":
        run_command("uci delete remotbot.main.mac_whitelist 2>/dev/null; uci commit remotbot")
        await query.answer("🗑 Whitelist dikosongkan!")
        await query.edit_message_text(get_whitelist_status(), parse_mode='HTML', reply_markup=get_device_manage_keyboard()); return

    if cb == "unblock_all":
        for mac in get_blocked_macs():
            unblock_mac(mac)
        await query.answer("🔓 Semua device di-unblokir!")
        await query.edit_message_text(get_whitelist_status(), parse_mode='HTML', reply_markup=get_device_manage_keyboard()); return
    if cb == "show_whitelist":
        wl = cfg.get("mac_whitelist",[])
        text = ("📋 <b>MAC Whitelist:</b>\n\n" + "\n".join(f"✅ <code>{m}</code>" for m in wl) if wl else t("whitelist_empty",cfg))
        await query.edit_message_text(text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back_menu",cfg),callback_data="block_menu")]])); return
    if cb.startswith("unblock_"):
        mac = cb[8:]; unblock_mac(mac); cfg2 = load_config()
        await query.edit_message_text(t("device_allowed",cfg2,mac=mac), parse_mode='HTML', reply_markup=get_block_keyboard(cfg2)); return
    if cb.startswith("quick_block_"):
        parts = cb.split("_",3); mac = parts[2]; ip = parts[3] if len(parts)>3 else "?"
        block_mac(mac); monitor_state["alerted_macs"].discard(mac)
        await query.edit_message_text(t("device_blocked",cfg,mac=mac,ip=ip), parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back_menu",cfg),callback_data="back_to_menu")]])); return
    if cb.startswith("quick_allow_"):
        mac = cb[12:]; add_to_whitelist(mac); monitor_state["alerted_macs"].discard(mac)
        await query.edit_message_text(t("device_allowed",cfg,mac=mac), parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back_menu",cfg),callback_data="back_to_menu")]])); return
    if cb == "service_control":
        await query.edit_message_text("🔧 <b>SERVICE CONTROL</b>\n\nPilih service:",
            parse_mode='HTML', reply_markup=get_service_control_keyboard(cfg)); return
    if cb.startswith("svc_"):
        parts = cb.split("_",2)
        if len(parts) == 3:
            action, svc = parts[1], parts[2]
            if action == "info":
                st = run_command(f"service {svc} status 2>&1")
                await query.edit_message_text(f"⚙️ <b>Service Info</b>\n\n<code>{svc}</code>\n\n<code>{st}</code>",
                    parse_mode='HTML', reply_markup=get_service_control_keyboard(cfg))
            else:
                loading = await query.edit_message_text(t("processing",cfg))
                await loading.edit_text(service_control(svc,action), parse_mode='HTML', reply_markup=get_service_control_keyboard(cfg))
        return

    loading = await query.edit_message_text(t("loading",cfg))
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
        "containers":   (get_container_info, get_main_keyboard),
    }
    if cb == "command":
        await loading.edit_text("💻 <b>Command Mode</b>\n\nFormat: <code>/cmd your_command</code>\nContoh: <code>/cmd uptime</code>",
            parse_mode='HTML', reply_markup=get_main_keyboard(cfg)); return
    if cb in handlers:
        fn, kb_fn = handlers[cb]
        try:
            result = fn(); keyboard = kb_fn(cfg)
            if len(result) > 4000:
                chunks = [result[i:i+4000] for i in range(0,len(result),4000)]
                await loading.edit_text(chunks[0], parse_mode='HTML', reply_markup=keyboard)
                for chunk in chunks[1:]: await query.message.reply_text(chunk, parse_mode='HTML')
            else:
                await loading.edit_text(result, parse_mode='HTML', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Callback error {cb}: {e}")
            await loading.edit_text(f"{t('error',cfg)}: {str(e)}", parse_mode='HTML', reply_markup=get_main_keyboard(cfg))

async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; cfg = load_config()
    if not check_auth(uid): await update.message.reply_text("❌ Unauthorized!"); return
    if not context.args: await update.message.reply_text(t("cmd_format",cfg), parse_mode='HTML'); return
    command = ' '.join(context.args)
    if any(c in command.lower() for c in ['rm -rf','dd if=','mkfs','format','> /dev/']):
        await update.message.reply_text(t("cmd_blocked",cfg)); return
    loading = await update.message.reply_text(t("executing",cfg))
    result  = run_command(command)
    if len(result) > 4000: result = result[:4000] + "\n... (truncated)"
    await loading.edit_text(f"💻 <b>Command:</b> <code>{command}</code>\n\n<b>Output:</b>\n<code>{result}</code>", parse_mode='HTML')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# ==================== MAIN ====================

def main():
    cfg = load_config()
    if not cfg.get("bot_token",""): logger.error("BOT_TOKEN belum dikonfigurasi!"); return
    app = Application.builder().token(cfg["bot_token"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cmd", cmd_handler))
    app.add_handler(MessageHandler(filters.Regex('^(📋 Menu|ℹ️ Help|🔄 Refresh)$'), handle_keyboard_button))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    async def post_init(application):
        asyncio.create_task(monitor_loop(application))
    app.post_init = post_init
    logger.info("RemotWRT Bot started with background monitor!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
