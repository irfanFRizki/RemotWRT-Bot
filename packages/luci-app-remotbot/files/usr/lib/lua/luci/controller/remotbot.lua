module("luci.controller.remotbot", package.seeall)

function index()
    if not nixio.fs.access("/etc/config/remotbot") then
        return
    end

    local page
    page = entry({"admin", "services", "remotbot"},
        alias("admin", "services", "remotbot", "dashboard"),
        _("Remot Bot"), 60)
    page.dependent = true
    page.acl_depends = { "luci-app-remotbot" }

    entry({"admin", "services", "remotbot", "dashboard"},
        form("remotbot/dashboard"),
        _("Dashboard"), 10).leaf = true

    entry({"admin", "services", "remotbot", "settings"},
        cbi("remotbot/settings"),
        _("Settings"), 20).leaf = true

    entry({"admin", "services", "remotbot", "action"},
        call("action_service"), nil).leaf = true
end

function action_service()
    local action = luci.http.formvalue("action") or ""
    local allowed = {start=1, stop=1, restart=1, status=1}
    local result = ""

    if allowed[action] then
        local cmd = "/etc/init.d/remotbot " .. action .. " 2>&1"
        local f = io.popen(cmd)
        result = f:read("*a")
        f:close()
    end

    luci.http.prepare_content("application/json")
    luci.http.write('{"result":' .. luci.json.stringify(result) .. '}')
end
