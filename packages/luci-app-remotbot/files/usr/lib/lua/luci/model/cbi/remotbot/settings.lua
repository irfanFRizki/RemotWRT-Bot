m = Map("remotbot", translate("Remot Bot — Settings"),
    translate("Konfigurasi Telegram Bot. Setelah simpan, buka Dashboard dan klik Start."))

s = m:section(NamedSection, "main", "remotbot", translate("Konfigurasi Bot"))
s.anonymous  = false
s.addremove  = false

-- Enable
o = s:option(Flag, "enabled", translate("Aktifkan Bot"),
    translate("Auto-start saat boot."))
o.default  = "0"
o.rmempty  = false

-- Bot Token
o = s:option(Value, "bot_token", translate("Telegram Bot Token"),
    translate("Dapatkan dari @BotFather di Telegram."))
o.password   = true
o.placeholder = "Contoh: 1234567890:AAECVsHHxxxx"
o.rmempty    = false

-- Allowed Users
o = s:option(Value, "allowed_users", translate("Allowed User IDs"),
    translate("User ID Telegram yang boleh pakai bot (pisah spasi). Cari via @userinfobot."))
o.placeholder = "Contoh: 5645537022"
o.rmempty    = false

-- CGI Path
o = s:option(Value, "cgi_online_path", translate("Path CGI Online Users"))
o.default     = "/www/cgi-bin/online"
o.placeholder = "/www/cgi-bin/online"

-- Log Level
o = s:option(ListValue, "log_level", translate("Level Log"))
o:value("DEBUG",   "DEBUG")
o:value("INFO",    "INFO (default)")
o:value("WARNING", "WARNING")
o:value("ERROR",   "ERROR")
o.default = "INFO"

return m
