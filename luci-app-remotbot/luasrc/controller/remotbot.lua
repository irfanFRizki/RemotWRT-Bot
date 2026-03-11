module("luci.controller.remotbot", package.seeall)

function index()
    if not nixio.fs.access("/etc/config/remotbot") then
        return
    end

    local page = entry({"admin", "services", "remotbot"}, firstchild(), _("Remot Bot"), 60)
    page.dependent = false
    page.acl_depends = { "luci-app-remotbot" }

    entry({"admin", "services", "remotbot", "dashboard"}, template("remotbot/dashboard"), _("Dashboard"), 1)
    entry({"admin", "services", "remotbot", "settings"}, cbi("remotbot/settings"), _("Settings"), 2)

    -- API endpoints
    entry({"admin", "services", "remotbot", "api", "status"}, call("action_status")).leaf = true
    entry({"admin", "services", "remotbot", "api", "start"}, call("action_start")).leaf = true
    entry({"admin", "services", "remotbot", "api", "stop"}, call("action_stop")).leaf = true
    entry({"admin", "services", "remotbot", "api", "restart"}, call("action_restart")).leaf = true
    entry({"admin", "services", "remotbot", "api", "install_deps"}, call("action_install_deps")).leaf = true
end

function action_status()
    local sys = require "luci.sys"
    local result = {}

    -- Check if running
    local pid_file = "/var/run/remotbot.pid"
    local running = false
    local pid = ""

    if nixio.fs.access(pid_file) then
        pid = sys.exec("cat " .. pid_file):gsub("\n","")
        if pid ~= "" then
            local check = sys.exec("kill -0 " .. pid .. " 2>&1")
            running = (check == "")
        end
    end

    -- Check config
    local config_ok = false
    local token_set = false
    local users_set = false

    if nixio.fs.access("/etc/remotbot/config.json") then
        config_ok = true
        local cfg_content = sys.exec("cat /etc/remotbot/config.json")
        local token = cfg_content:match('"bot_token"%s*:%s*"([^"]+)"')
        token_set = (token ~= nil and token ~= "")

        local users = cfg_content:match('"allowed_users"%s*:%s*%[([^%]]+)%]')
        users_set = (users ~= nil and users:match("%d+") ~= nil)
    end

    -- Check python deps
    local deps_ok = sys.exec("python3 -c 'from telegram.ext import Application' 2>&1") == ""

    result = {
        running = running,
        pid = pid,
        config_ok = config_ok,
        token_set = token_set,
        users_set = users_set,
        deps_ok = deps_ok,
        uptime = running and sys.exec("ps | grep pi4Bot | grep -v grep | awk '{print $1}'"):gsub("\n","") or ""
    }

    luci.http.prepare_content("application/json")
    luci.http.write(require("luci.jsonc").stringify(result))
end

function action_start()
    local sys = require "luci.sys"
    sys.exec("/etc/init.d/remotbot start")
    luci.http.prepare_content("application/json")
    luci.http.write('{"ok":true}')
end

function action_stop()
    local sys = require "luci.sys"
    sys.exec("/etc/init.d/remotbot stop")
    luci.http.prepare_content("application/json")
    luci.http.write('{"ok":true}')
end

function action_restart()
    local sys = require "luci.sys"
    sys.exec("/etc/init.d/remotbot restart")
    luci.http.prepare_content("application/json")
    luci.http.write('{"ok":true}')
end

function action_install_deps()
    local sys = require "luci.sys"
    -- Run in background
    sys.exec("sh /usr/bin/remotbot-install-deps > /tmp/remotbot-install.log 2>&1 &")
    luci.http.prepare_content("application/json")
    luci.http.write('{"ok":true,"message":"Installing dependencies in background. Check /tmp/remotbot-install.log"}')
end
