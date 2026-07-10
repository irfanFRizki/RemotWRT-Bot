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
    
    -- API endpoints (protected by LuCI session)
    entry({"admin", "services", "remotwrt", "api"}, call("api_remotwrt")).leaf = true
end

function api_remotwrt()
    local http = require "luci.http"
    local json = require "luci.jsonc"
    local util = require "luci.util"
    
    -- CSRF Protection: Verify token for POST requests
    local token = http.formvalue("token")
    local method = http.getenv("REQUEST_METHOD")
    
    if method == "POST" then
        local disp = require "luci.dispatcher"
        local expected_token = disp.token()
        if not token or token ~= expected_token then
            http.status(403, "Forbidden")
            http.write_json({success = false, error = "Invalid CSRF token"})
            return
        end
    end
    
    local action = http.formvalue("action")
    local response = {}
    
    if action == "get_devices" then
        response = get_connected_devices()
    elseif action == "generate_voucher" then
        local category = http.formvalue("category")
        local validity = http.formvalue("validity")
        local max_use = http.formvalue("max_use")
        response = generate_voucher_code(category, validity, max_use)
    elseif action == "add_voucher" then
        local code = http.formvalue("code")
        local category = http.formvalue("category")
        response = add_voucher(code, category)
    elseif action == "delete_voucher" then
        local code = http.formvalue("code")
        response = delete_voucher(code)
    elseif action == "add_firewall_rule" then
        local rule_type = http.formvalue("rule_type")
        local mac = http.formvalue("mac")
        local ip = http.formvalue("ip")
        response = add_firewall_rule(rule_type, mac, ip)
    elseif action == "remove_firewall_rule" then
        local rule_type = http.formvalue("rule_type")
        local ip = http.formvalue("ip")
        response = remove_firewall_rule(rule_type, ip)
    end
    
    http.prepare_content("application/json")
    http.write_json(response)
end

-- Seed random number generator
math.randomseed(os.time())

function get_connected_devices()
    local devices = {}
    
    -- Get from OpenNDS using JSON output (more reliable)
    local nds = io.popen("ndsctl clients json 2>/dev/null || ndsctl clients 2>/dev/null | grep -E '^[0-9]' || true")
    if nds then
        for line in nds:lines() do
            -- Try to parse JSON first, fallback to text parsing
            local ip, mac
            if line:match("{") then
                -- JSON format
                local json = require "luci.jsonc"
                local data = json.parse(line)
                if data and data.ip and data.mac then
                    ip = data.ip
                    mac = data.mac
                end
            else
                -- Text format: IP MAC hostname status
                local parts = {}
                for part in line:gmatch("%S+") do
                    table.insert(parts, part)
                end
                if #parts >= 2 then
                    ip = parts[1]
                    mac = parts[2]
                end
            end
            
            if ip and mac then
                table.insert(devices, {
                    ip = ip,
                    mac = mac,
                    status = "authenticated",
                    source = "opennds"
                })
            end
        end
        nds:close()
    end
    
    -- Get from ARP table
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

-- Helper function to validate IPv4 address
local function is_valid_ipv4(ip)
    if not ip then return false end
    local pattern = "^%d%d?%d?%.%d%d?%d?%.%d%d?%d?%.%d%d?%d?$"
    if not ip:match(pattern) then return false end
    
    -- Check each octet is 0-255
    for octet in ip:gmatch("([^%.]+)") do
        local num = tonumber(octet)
        if not num or num < 0 or num > 255 then
            return false
        end
    end
    return true
end

-- Helper function to validate MAC address
local function is_valid_mac(mac)
    if not mac then return false end
    local pattern = "^%x%x:%x%x:%x%x:%x%x:%x%x:%x%x$"
    return mac:match(pattern) ~= nil
end

-- Helper function to validate voucher code (alphanumeric only)
local function is_valid_voucher_code(code)
    if not code then return false end
    -- Only allow alphanumeric characters, length 4-20
    return code:match("^[%w]+$") and #code >= 4 and #code <= 20
end

-- Helper function to safely write voucher to file
local function write_voucher_to_file(code, category)
    local fs = require "nixio.fs"
    local file_path = "/etc/voucher_keluarga.txt"
    
    if category ~= "keluarga" then
        return true -- Only keluarga category uses file
    end
    
    -- Read existing vouchers
    local existing = {}
    local file = io.open(file_path, "r")
    if file then
        for line in file:lines() do
            if line and line ~= "" then
                table.insert(existing, line)
            end
        end
        file:close()
    end
    
    -- Check if already exists
    for _, v in ipairs(existing) do
        if v == code then
            return true -- Already exists
        end
    end
    
    -- Append new voucher
    file = io.open(file_path, "a")
    if file then
        file:write(code .. "\n")
        file:close()
        return true
    end
    
    return false
end

-- Helper function to remove voucher from file
local function remove_voucher_from_file(code)
    local fs = require "nixio.fs"
    local file_path = "/etc/voucher_keluarga.txt"
    local temp_path = "/tmp/voucher_temp.txt"
    
    if not fs.access(file_path) then
        return true -- File doesn't exist, nothing to remove
    end
    
    -- Read and filter out the voucher
    local file = io.open(file_path, "r")
    local temp = io.open(temp_path, "w")
    
    if not file or not temp then
        if file then file:close() end
        if temp then temp:close() end
        return false
    end
    
    for line in file:lines() do
        if line and line ~= code then
            temp:write(line .. "\n")
        end
    end
    
    file:close()
    temp:close()
    
    -- Replace original file
    os.execute("mv " .. temp_path .. " " .. file_path)
    return true
end

function generate_voucher_code(category, validity, max_use)
    local uci = require "luci.model.uci".cursor()
    
    -- Validate inputs
    if not category or (category ~= "keluarga" and category ~= "pengguna_lain") then
        return {success = false, error = "Invalid category"}
    end
    
    local validity_num = tonumber(validity)
    if not validity_num or validity_num < 1 or validity_num > 10080 then
        validity_num = 60 -- Default 60 minutes
    end
    
    local max_use_num = tonumber(max_use)
    if not max_use_num or max_use_num < 1 or max_use_num > 1000 then
        max_use_num = 1
    end
    
    -- Generate unique 8-character alphanumeric code
    local chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" -- Exclude similar chars (I,1,O,0)
    local code = ""
    for i = 1, 8 do
        local idx = math.random(1, #chars)
        code = code .. chars:sub(idx, idx)
    end
    
    -- Add timestamp prefix for uniqueness
    code = code .. string.format("%02X", os.time() % 256)
    
    -- Save to UCI config
    local section_id = uci:add("remotwrt", "voucher")
    uci:set("remotwrt", section_id, "code", code)
    uci:set("remotwrt", section_id, "category", category)
    uci:set("remotwrt", section_id, "validity", tostring(validity_num))
    uci:set("remotwrt", section_id, "max_use", tostring(max_use_num))
    uci:set("remotwrt", section_id, "uses", "0")
    uci:set("remotwrt", section_id, "created", tostring(os.time()))
    uci:set("remotwrt", section_id, "status", "active")
    uci:commit("remotwrt")
    
    -- Also write to file for keluarga category (for voucher_auth.sh compatibility)
    if category == "keluarga" then
        write_voucher_to_file(code, category)
    end
    
    return {
        success = true,
        code = code,
        category = category,
        validity = validity_num,
        max_use = max_use_num
    }
end

function add_voucher(code, category)
    local uci = require "luci.model.uci".cursor()
    
    -- Validate inputs
    if not is_valid_voucher_code(code) then
        return {success = false, error = "Invalid voucher code format"}
    end
    
    if not category or (category ~= "keluarga" and category ~= "pengguna_lain") then
        return {success = false, error = "Invalid category"}
    end
    
    -- Check if code already exists
    local exists = false
    uci:foreach("remotwrt", "voucher", function(section)
        if section.code == code then
            exists = true
        end
    end)
    
    if exists then
        return {success = false, error = "Voucher code already exists"}
    end
    
    -- Save to UCI config
    local section_id = uci:add("remotwrt", "voucher")
    uci:set("remotwrt", section_id, "code", code)
    uci:set("remotwrt", section_id, "category", category)
    uci:set("remotwrt", section_id, "validity", "60")
    uci:set("remotwrt", section_id, "max_use", "1")
    uci:set("remotwrt", section_id, "uses", "0")
    uci:set("remotwrt", section_id, "created", tostring(os.time()))
    uci:set("remotwrt", section_id, "status", "active")
    uci:commit("remotwrt")
    
    -- Also write to file for keluarga category
    if category == "keluarga" then
        write_voucher_to_file(code, category)
    end
    
    return {success = true, message = "Voucher added successfully", code = code}
end

function delete_voucher(code)
    local uci = require "luci.model.uci".cursor()
    
    if not is_valid_voucher_code(code) then
        return {success = false, error = "Invalid voucher code format"}
    end
    
    local found = false
    uci:foreach("remotwrt", "voucher", function(section)
        if section.code == code then
            found = true
            uci:delete("remotwrt", section[".name"])
        end
    end)
    
    if found then
        uci:commit("remotwrt")
        -- Also remove from file
        remove_voucher_from_file(code)
        return {success = true, message = "Voucher deleted successfully"}
    end
    
    return {success = false, error = "Voucher not found"}
end

function add_firewall_rule(rule_type, mac, ip)
    local uci = require "luci.model.uci".cursor()
    
    -- Validate inputs
    if not rule_type or (rule_type ~= "whitelist" and rule_type ~= "blacklist") then
        return {success = false, error = "Invalid rule type"}
    end
    
    if not is_valid_mac(mac) then
        return {success = false, error = "Invalid MAC address format"}
    end
    
    if ip and not is_valid_ipv4(ip) then
        return {success = false, error = "Invalid IP address format"}
    end
    
    -- Add to UCI config (remotwrt firewall section)
    local section_id = uci:add("remotwrt", "firewall_" .. rule_type)
    uci:set("remotwrt", section_id, "mac", mac)
    uci:set("remotwrt", section_id, "ip", ip or "")
    uci:set("remotwrt", section_id, "enabled", "1")
    uci:commit("remotwrt")
    
    -- Also add to OpenWRT firewall config for immediate effect
    local fw_uci = require "luci.model.uci".cursor()
    local fw_section = fw_uci:add("firewall", "rule")
    fw_uci:set("firewall", fw_section, "name", "RemotWRT_" .. rule_type .. "_" .. mac:gsub(":", ""))
    fw_uci:set("firewall", fw_section, "target", rule_type == "whitelist" and "ACCEPT" or "DROP")
    fw_uci:set("firewall", fw_section, "src", "lan")
    fw_uci:set("firewall", fw_section, "proto", "all")
    if ip then
        fw_uci:set("firewall", fw_section, "src_ip", ip)
    end
    fw_uci:set("firewall", fw_section, "src_mac", mac)
    fw_uci:commit("firewall")
    
    -- Reload firewall to apply changes immediately
    os.execute("/etc/init.d/firewall reload >/dev/null 2>&1")
    
    return {success = true, message = "Rule added successfully", section = fw_section}
end

function remove_firewall_rule(rule_type, ip)
    local uci = require "luci.model.uci".cursor()
    
    if not rule_type or (rule_type ~= "whitelist" and rule_type ~= "blacklist") then
        return {success = false, error = "Invalid rule type"}
    end
    
    if ip and not is_valid_ipv4(ip) then
        return {success = false, error = "Invalid IP address format"}
    end
    
    local removed = false
    
    -- Remove from remotwrt config
    uci:foreach("remotwrt", "firewall_" .. rule_type, function(section)
        if (not ip or section.ip == ip) then
            uci:delete("remotwrt", section[".name"])
            removed = true
        end
    end)
    
    if removed then
        uci:commit("remotwrt")
    end
    
    -- Remove from OpenWRT firewall config
    local fw_uci = require "luci.model.uci".cursor()
    fw_uci:foreach("firewall", "rule", function(section)
        if section.name and section.name:match("^RemotWRT_" .. rule_type) then
            if not ip or section.src_ip == ip then
                fw_uci:delete("firewall", section[".name"])
            end
        end
    end)
    fw_uci:commit("firewall")
    
    -- Reload firewall
    os.execute("/etc/init.d/firewall reload >/dev/null 2>&1")
    
    return {success = true, message = "Rule removed successfully"}
end
