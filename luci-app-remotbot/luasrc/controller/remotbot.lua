module("luci.controller.remotbot", package.seeall)
function index()
    if not nixio.fs.access("/etc/config/remotbot") then return end
    local page = entry({"admin","services","remotbot"}, firstchild(), _("Remot Bot"), 60)
    page.dependent = false
    entry({"admin","services","remotbot","dashboard"}, template("remotbot/dashboard"), _("Dashboard"), 1)
    entry({"admin","services","remotbot","settings"},  cbi("remotbot/settings"),      _("Settings"),  2)
    entry({"admin","services","remotbot","api","status"},      call("action_status")).leaf      = true
    entry({"admin","services","remotbot","api","start"},       call("action_start")).leaf       = true
    entry({"admin","services","remotbot","api","stop"},        call("action_stop")).leaf        = true
    entry({"admin","services","remotbot","api","restart"},     call("action_restart")).leaf     = true
    entry({"admin","services","remotbot","api","install_deps"},call("action_install_deps")).leaf = true
end
function action_status()
    local sys=require "luci.sys"; local pid_file="/var/run/remotbot.pid"; local running=false; local pid=""
    if nixio.fs.access(pid_file) then
        pid=sys.exec("cat "..pid_file):gsub("\n","")
        if pid~="" then running=(sys.exec("kill -0 "..pid.." 2>&1")==""  ) end
    end
    local cfg_content=nixio.fs.access("/etc/remotbot/config.json") and sys.exec("cat /etc/remotbot/config.json") or ""
    local token=cfg_content:match('"bot_token"%s*:%s*"([^"]+)"')
    local deps_ok=sys.exec("python3 -c 'from telegram.ext import Application' 2>&1")==""
    luci.http.prepare_content("application/json")
    luci.http.write(require("luci.jsonc").stringify({running=running,pid=pid,token_set=(token~=nil and token~=""),deps_ok=deps_ok}))
end
function action_start()        require("luci.sys").exec("/etc/init.d/remotbot start");   luci.http.prepare_content("application/json"); luci.http.write('{"ok":true}') end
function action_stop()         require("luci.sys").exec("/etc/init.d/remotbot stop");    luci.http.prepare_content("application/json"); luci.http.write('{"ok":true}') end
function action_restart()      require("luci.sys").exec("/etc/init.d/remotbot restart"); luci.http.prepare_content("application/json"); luci.http.write('{"ok":true}') end
function action_install_deps() require("luci.sys").exec("sh /usr/bin/remotbot-install-deps > /tmp/remotbot-install.log 2>&1 &"); luci.http.prepare_content("application/json"); luci.http.write('{"ok":true}') end
