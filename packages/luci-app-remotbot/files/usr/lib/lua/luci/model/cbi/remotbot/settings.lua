m = Map("remotbot", translate("Remot Bot — Settings"),
    translate("Konfigurasi Telegram Bot. Setelah simpan, buka Dashboard dan klik Start."))
s = m:section(NamedSection, "main", "remotbot", translate("Konfigurasi Bot"))
s.anonymous = false; s.addremove = false

o = s:option(Flag, "enabled", translate("Aktifkan Bot"), translate("Auto-start saat boot."))
o.default = "0"; o.rmempty = false

o = s:option(Value, "bot_token", translate("Telegram Bot Token"),
    translate("Dapatkan dari @BotFather di Telegram."))
o.password = true; o.placeholder = "Contoh: 1234567890:AAECVsHHxxxx"; o.rmempty = false

o = s:option(Value, "allowed_users", translate("Allowed User IDs"),
    translate("User ID Telegram (pisah spasi). Cari via @userinfobot."))
o.placeholder = "Contoh: 5645537022"; o.rmempty = false

o = s:option(Value, "cgi_online_path", translate("Path CGI Online Users"))
o.default = "/www/cgi-bin/online"; o.placeholder = "/www/cgi-bin/online"

o = s:option(ListValue, "language", translate("Bahasa / Language"))
o:value("id", "Indonesia 🇮🇩"); o:value("en", "English 🇬🇧"); o.default = "id"

s2 = m:section(NamedSection, "main", "remotbot", translate("Notifikasi Otomatis"))
s2.anonymous = false; s2.addremove = false

o = s2:option(Flag, "notify_cpu_temp", translate("Alert CPU Panas"))
o.default = "1"; o.rmempty = false
o = s2:option(Value, "cpu_temp_threshold", translate("Batas Suhu CPU (°C)"))
o.default = "75"; o.datatype = "uinteger"

o = s2:option(Flag, "notify_ram", translate("Alert RAM Penuh"))
o.default = "1"; o.rmempty = false
o = s2:option(Value, "ram_threshold", translate("Batas RAM (%)"))
o.default = "85"; o.datatype = "uinteger"

o = s2:option(Flag, "notify_wan", translate("Alert WAN Putus"))
o.default = "1"; o.rmempty = false
o = s2:option(Value, "wan_timeout_minutes", translate("Alert WAN setelah (menit)"))
o.default = "60"; o.datatype = "uinteger"

o = s2:option(Flag, "notify_unknown_device", translate("Alert Device Tak Dikenal"))
o.default = "1"; o.rmempty = false

return m
