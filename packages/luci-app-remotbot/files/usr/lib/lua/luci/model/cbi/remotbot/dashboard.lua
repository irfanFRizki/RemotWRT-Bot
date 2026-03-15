local fs   = require "nixio.fs"
local sys  = require "luci.sys"
local http = require "luci.http"

-- Jalankan action jika ada POST
local action = http.formvalue("action")
if action == "start" then
    sys.call("/etc/init.d/remotbot start 2>/dev/null")
elseif action == "stop" then
    sys.call("/etc/init.d/remotbot stop 2>/dev/null")
elseif action == "restart" then
    sys.call("/etc/init.d/remotbot restart 2>/dev/null")
end

-- Cek status
local pid_file = "/var/run/remotbot.pid"
local running  = false
if fs.access(pid_file) then
    local pid = fs.readfile(pid_file) or ""
    pid = pid:gsub("%s+", "")
    if pid ~= "" then
        running = (sys.call("kill -0 " .. pid .. " 2>/dev/null") == 0)
    end
end

local bot_token    = luci.sys.exec("uci -q get remotbot.main.bot_token 2>/dev/null"):gsub("%s+$","")
local allowed      = luci.sys.exec("uci -q get remotbot.main.allowed_users 2>/dev/null"):gsub("%s+$","")
local enabled      = luci.sys.exec("uci -q get remotbot.main.enabled 2>/dev/null"):gsub("%s+$","")

m = SimpleForm("remotbot_dash", translate("Remot Bot — Dashboard"))
m.reset  = false
m.submit = false

-- Status section
s = m:section(SimpleSection)
s.template = "remotbot/dashboard_status"
s.running   = running
s.bot_token = bot_token
s.allowed   = allowed
s.enabled   = (enabled == "1")

return m
