module("luci.controller.remotwrt", package.seeall)

function index()
    if not nixio.fs.access("/etc/config/remotwrt") then
        return
    end

    entry({"admin", "services", "remotwrt"}, alias("admin", "services", "remotwrt", "dashboard"), _("RemotWRT WiFi"), 10).dependent = true
    entry({"admin", "services", "remotwrt", "dashboard"}, template("remotwrt/dashboard"), _("Dashboard"), 1).leaf = true
    entry({"admin", "services", "remotwrt", "vouchers"}, cbi("remotwrt/vouchers"), _("Voucher Manager"), 2).leaf = true
    entry({"admin", "services", "remotwrt", "firewall"}, cbi("remotwrt/firewall"), _("Firewall Rules"), 3).leaf = true
    entry({"admin", "services", "remotwrt", "settings"}, cbi("remotwrt/settings"), _("Settings"), 4).leaf = true
    entry({"admin", "services", "remotwrt", "history"}, template("remotwrt/history"), _("Device History"), 5).leaf = true
    
    -- API endpoints
    entry({"admin", "services", "remotwrt", "api"}, call("api_remotwrt")).leaf = true
end

function api_remotwrt()
    local http = require "luci.http"
    local json = require "luci.jsonc"
    
    local action = http.formvalue("action")
    local response = {}
    
    if action == "get_devices" then
        response = get_connected_devices()
    elseif action == "generate_voucher" then
        local category = http.formvalue("category")
        local validity = http.formvalue("validity")
        response = generate_voucher_code(category, validity)
    elseif action == "add_firewall_rule" then
        local rule_type = http.formvalue("rule_type")
        local mac = http.formvalue("mac")
        local ip = http.formvalue("ip")
        response = add_firewall_rule(rule_type, mac, ip)
    end
    
    http.prepare_content("application/json")
    http.write_json(response)
end

function get_connected_devices()
    local devices = {}
    
    -- Get from OpenNDS
    local nds = io.popen("ndsctl clients 2>/dev/null | grep -E '^[0-9]' || true")
    if nds then
        for line in nds:lines() do
            local parts = {}
            for part in line:gmatch("%S+") do
                table.insert(parts, part)
            end
            if #parts >= 2 then
                table.insert(devices, {
                    ip = parts[1],
                    mac = parts[2],
                    status = "authenticated",
                    source = "opennds"
                })
            end
        end
        nds:close()
    end
    
    -- Get from ARP
    local arp = io.popen("cat /proc/net/arp 2>/dev/null | grep -v '^IP' | grep -v '00:00:00:00:00:00' || true")
    if arp then
        for line in arp:lines() do
            local parts = {}
            for part in line:gmatch("%S+") do
                table.insert(parts, part)
            end
            if #parts >= 4 then
                local found = false
                for _, dev in ipairs(devices) do
                    if dev.mac == parts[4] then
                        found = true
                        break
                    end
                end
                if not found then
                    table.insert(devices, {
                        ip = parts[1],
                        mac = parts[4],
                        status = "pending",
                        source = "arp"
                    })
                end
            end
        end
        arp:close()
    end
    
    return devices
end

function generate_voucher_code(category, validity)
    local code = os.date("%Y%m%d%H%M%S") .. math.random(1000, 9999)
    code = code:sub(1, 8)
    
    return {
        success = true,
        code = code,
        category = category,
        validity = validity
    }
end

function add_firewall_rule(rule_type, mac, ip)
    local uci = require "luci.model.uci".cursor()
    local section_id = uci:add("remotwrt", "firewall_" .. rule_type)
    
    uci:set("remotwrt", section_id, "mac", mac)
    uci:set("remotwrt", section_id, "ip", ip)
    uci:set("remotwrt", section_id, "enabled", "1")
    uci:commit("remotwrt")
    
    return {success = true, message = "Rule added successfully"}
end
