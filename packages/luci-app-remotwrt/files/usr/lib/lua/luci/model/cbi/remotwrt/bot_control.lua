-- CBI Model: remotwrt/bot_control
-- Migrasi dari luci-app-remotbot: konfigurasi Telegram Bot (token, allowed users,
-- notification thresholds) dan kontrol service remotbot (start/stop/restart).
-- Ditambahkan ke luci-app-remotwrt sebagai tab terpadu.

local fs   = require "nixio.fs"
local sys  = require "luci.sys"
local http = require "luci.http"

-- Handle start/stop/restart actions
local csrf_error = false
local action = http.formvalue("action")
if action then
    local token = http.formvalue("token")
    local disp = require "luci.dispatcher"
    local expected_token = disp.token()
    if not token or token ~= expected_token then
        csrf_error = true
    else
        if action == "start" then
            sys.call("/etc/init.d/remotbot start 2>/dev/null")
        elseif action == "stop" then
            sys.call("/etc/init.d/remotbot stop 2>/dev/null")
        elseif action == "restart" then
            sys.call("/etc/init.d/remotbot restart 2>/dev/null")
        end
    end
end

-- Check running status via PID file
local running = false
local pid_file = "/var/run/remotbot.pid"
if fs.access(pid_file) then
    local pid = (fs.readfile(pid_file) or ""):gsub("%s+", "")
    if pid ~= "" then
        running = (sys.call("kill -0 " .. pid .. " 2>/dev/null") == 0)
    end
end

-- === Bot Control Section ===
m = SimpleForm("remotbot_control", translate("Telegram Bot Control"),
    translate("Kontrol dan konfigurasi Telegram Bot untuk monitoring OpenWrt."))
m.reset = false
m.submit = false

if csrf_error then
    m.errmessage = translate("Error: Token CSRF tidak valid atau kedaluwarsa.")
end

-- Status & control buttons
s = m:section(SimpleSection)
s.template = "remotwrt/bot_control"
s.running  = running

-- === Bot Configuration Map ===
m2 = Map("remotbot", translate("Konfigurasi Bot"),
    translate("Pengaturan Telegram Bot. Setelah simpan, gunakan tombol di atas untuk Start."))

s2 = m2:section(NamedSection, "main", "remotbot", translate("Pengaturan Utama"))
s2.anonymous = false
s2.addremove = false

o = s2:option(Flag, "enabled", translate("Aktifkan Bot"),
    translate("Auto-start saat boot."))
o.default  = "0"
o.rmempty  = false

o = s2:option(Value, "bot_token", translate("Telegram Bot Token"),
    translate("Dapatkan dari @BotFather di Telegram."))
o.password   = true
o.placeholder = "Contoh: 1234567890:AAECVsHHxxxx"
o.rmempty    = false

o = s2:option(Value, "allowed_users", translate("Allowed User IDs"),
    translate("User ID Telegram yang diizinkan (pisah spasi). Cari via @userinfobot."))
o.placeholder = "Contoh: 5645537022"
o.rmempty    = false

o = s2:option(Value, "cgi_online_path", translate("Path CGI Online Users"))
o.default    = "/www/cgi-bin/online"
o.placeholder = "/www/cgi-bin/online"

o = s2:option(ListValue, "language", translate("Bahasa / Language"))
o:value("id", "Indonesia 🇮🇩")
o:value("en", "English 🇬🇧")
o.default = "id"

-- Notification thresholds
s3 = m2:section(NamedSection, "main", "remotbot", translate("Notifikasi Otomatis"))
s3.anonymous = false
s3.addremove = false

o = s3:option(Flag, "notify_cpu_temp", translate("Alert CPU Panas"))
o.default = "1"
o.rmempty = false

o = s3:option(Value, "cpu_temp_threshold", translate("Batas Suhu CPU (°C)"))
o.default  = "75"
o.datatype = "uinteger"

o = s3:option(Flag, "notify_ram", translate("Alert RAM Penuh"))
o.default = "1"
o.rmempty = false

o = s3:option(Value, "ram_threshold", translate("Batas RAM (%)"))
o.default  = "85"
o.datatype = "uinteger"

o = s3:option(Flag, "notify_wan", translate("Alert WAN Putus"))
o.default = "1"
o.rmempty = false

o = s3:option(Value, "wan_timeout_minutes", translate("Alert WAN setelah (menit)"))
o.default  = "60"
o.datatype = "uinteger"

o = s3:option(Flag, "notify_unknown_device", translate("Alert Device Tak Dikenal"))
o.default = "1"
o.rmempty = false

return m, m2
