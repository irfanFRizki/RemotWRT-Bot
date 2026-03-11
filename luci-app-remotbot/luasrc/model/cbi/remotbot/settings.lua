local sys = require "luci.sys"
local fs = require "nixio.fs"

-- Read current config
local config = {}
if fs.access("/etc/remotbot/config.json") then
    local content = fs.readfile("/etc/remotbot/config.json") or "{}"
    -- Simple JSON parse for our known fields
    local token = content:match('"bot_token"%s*:%s*"([^"]*)"') or ""
    local users_raw = content:match('"allowed_users"%s*:%s*%[([^%]]*)%]') or ""
    local cgi_path = content:match('"cgi_online_path"%s*:%s*"([^"]*)"') or "/www/cgi-bin/online"
    config.bot_token = token
    config.allowed_users = users_raw:gsub("%s","")
    config.cgi_online_path = cgi_path
end

m = Map("remotbot", translate("Remot Bot - Settings"),
    translate("Konfigurasi Telegram Bot untuk monitoring OpenWRT Raspberry Pi 4"))

-- Bot Configuration Section
s = m:section(NamedSection, "bot", "remotbot", translate("Bot Configuration"))
s.addremove = false
s.anonymous = true

o = s:option(Value, "bot_token", translate("Bot Token"),
    translate("Token dari @BotFather di Telegram. Format: <code>123456:ABC-DEF...</code>"))
o.password = true
o.rmempty = false
o.placeholder = "1234567890:AAABBB-CCCDDDEEE..."

o = s:option(Value, "allowed_users", translate("Allowed User IDs"),
    translate("Telegram User ID yang diizinkan (pisahkan dengan koma). Dapatkan ID dari @userinfobot"))
o.rmempty = false
o.placeholder = "123456789,987654321"

o = s:option(Value, "cgi_online_path", translate("CGI Online Path"),
    translate("Path ke script CGI untuk melihat user online"))
o.default = "/www/cgi-bin/online"

-- Service Control Section
s2 = m:section(NamedSection, "service", "remotbot", translate("Service Control"))
s2.addremove = false
s2.anonymous = true

-- Save config to JSON on submit
function m.on_commit(self)
    local token = m:get("bot", "bot_token") or ""
    local users_str = m:get("bot", "allowed_users") or ""
    local cgi_path = m:get("bot", "cgi_online_path") or "/www/cgi-bin/online"

    -- Parse users into JSON array
    local users_arr = "[]"
    local users_list = {}
    for uid in users_str:gmatch("(%d+)") do
        table.insert(users_list, uid)
    end
    if #users_list > 0 then
        users_arr = "[" .. table.concat(users_list, ",") .. "]"
    end

    -- Write config.json
    local json_content = string.format('{\n    "bot_token": "%s",\n    "allowed_users": %s,\n    "cgi_online_path": "%s"\n}\n',
        token, users_arr, cgi_path)

    fs.writefile("/etc/remotbot/config.json", json_content)
end

return m
