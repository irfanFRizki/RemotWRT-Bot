local sys=require "luci.sys"; local fs=require "nixio.fs"
local content=fs.access("/etc/remotbot/config.json") and (fs.readfile("/etc/remotbot/config.json") or "{}") or "{}"
m=Map("remotbot",translate("Remot Bot — Settings"),translate("Konfigurasi Telegram Bot untuk monitoring OpenWRT"))
s=m:section(NamedSection,"bot","remotbot",translate("Bot Configuration"))
s.addremove=false; s.anonymous=true
o=s:option(Value,"bot_token",translate("Bot Token"),translate("Token dari @BotFather")); o.password=true; o.rmempty=false; o.placeholder="1234567890:AAABBB..."
o=s:option(Value,"allowed_users",translate("Allowed User IDs"),translate("Telegram User ID (pisahkan koma). Dari @userinfobot")); o.rmempty=false; o.placeholder="123456789"
o=s:option(Value,"cgi_online_path",translate("CGI Online Path")); o.default="/www/cgi-bin/online"
function m.on_commit(self)
    local token=m:get("bot","bot_token") or ""; local users_str=m:get("bot","allowed_users") or ""; local cgi=m:get("bot","cgi_online_path") or "/www/cgi-bin/online"
    local users_list={}; for uid in users_str:gmatch("(%d+)") do table.insert(users_list,uid) end
    local users_arr=#users_list>0 and "["..table.concat(users_list,",").."]" or "[]"
    fs.writefile("/etc/remotbot/config.json",string.format('{\n    "bot_token": "%s",\n    "allowed_users": %s,\n    "cgi_online_path": "%s",\n    "language": "id",\n    "cpu_temp_threshold": 75,\n    "ram_threshold": 85,\n    "wan_timeout_minutes": 60,\n    "mac_whitelist": [],\n    "notify_cpu_temp": true,\n    "notify_ram": true,\n    "notify_wan": true,\n    "notify_unknown_device": true\n}\n',token,users_arr,cgi))
end
return m
