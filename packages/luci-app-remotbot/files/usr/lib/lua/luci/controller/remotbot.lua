module("luci.controller.remotbot", package.seeall)

function index()
    if not nixio.fs.access("/etc/config/remotbot") then
        return
    end

    local page
    page = entry({"admin", "services", "remotbot"},
        alias("admin", "services", "remotbot", "dashboard"),
        _("Remot Bot"), 60)
    page.dependent  = true
    page.acl_depends = { "luci-app-remotbot" }

    entry({"admin", "services", "remotbot", "dashboard"},
        form("remotbot/dashboard"),
        _("Dashboard"), 10).leaf = true

    entry({"admin", "services", "remotbot", "settings"},
        cbi("remotbot/settings"),
        _("Settings"), 20).leaf = true
end
