module("luci.controller.api.remotbot_pending", package.seeall)

-- API endpoint untuk read/write pending approval OpenNDS
-- Digunakan oleh LuCI web interface untuk manage device tanpa Telegram
--
-- PENTING:
--   Fitur ini tidak lagi menjadi mekanisme auth utama captive portal sejak sistem voucher (BinAuth)
--   diaktifkan. Sistem ini sekarang murni untuk observasi/monitoring dan override manual admin 
--   lewat Telegram (mis. blokir MAC address langsung), tidak menangani alur login WiFi tamu.

function index()
    -- Endpoint GET untuk baca semua pending entries
    entry({"admin", "services", "remotbot", "api", "pending"}, call("get_pending_list")).leaf = true
    
    -- Endpoint POST untuk approve/block device
    entry({"admin", "services", "remotbot", "api", "pending", ":mac"}, call("handle_action")).leaf = true
end

local fs = require "nixio.fs"
local jsonc = require "luci.jsonc"
local uci = require "luci.model.uci".cursor()

-- Path ke file JSON shared (sama dengan yang dipakai fas_server.py dan pi4Bot.py)
local PENDING_FILE = "/tmp/opennds_pending.json"

-- Helper: baca UCI config remotbot.main.fas_pending_file jika ada, fallback ke default
function get_pending_file_path()
    local custom_path = uci:get_first("remotbot", "main", "fas_pending_file")
    if custom_path and custom_path ~= "" then
        return custom_path
    end
    return PENDING_FILE
end

-- GET: Baca semua entries dari file JSON pending
function get_pending_list()
    local file_path = get_pending_file_path()
    local content = fs.readfile(file_path)
    
    if not content or content == "" then
        -- File belum ada atau kosong, return empty object
        luci.http.prepare_content("application/json")
        luci.http.write_json({})
        return
    end
    
    -- Parse JSON
    local success, data = pcall(jsonc.parse, content)
    if not success then
        -- JSON invalid/corrupt, return empty
        luci.http.prepare_content("application/json")
        luci.http.write_json({error = "Invalid JSON file"})
        return
    end
    
    -- Return data sebagai JSON response
    luci.http.prepare_content("application/json")
    luci.http.write_json(data or {})
end

-- POST: Handle approve/block action
function handle_action(mac)
    -- Validate MAC address format (basic check)
    if not mac or not mac:match("^[%x:]+$") then
        luci.http.status(400, "Bad Request")
        luci.http.prepare_content("application/json")
        luci.http.write_json({success = false, message = "Invalid MAC address"})
        return
    end
    
    -- Normalize MAC to uppercase
    mac = mac:upper()
    
    -- Read request body
    local length = tonumber(luci.http.getenv("CONTENT_LENGTH")) or 0
    local body = ""
    if length > 0 then
        body = luci.http.read(length)
    end
    
    -- Parse JSON body
    local success, request = pcall(jsonc.parse, body)
    if not success or not request or not request.action then
        luci.http.status(400, "Bad Request")
        luci.http.prepare_content("application/json")
        luci.http.write_json({success = false, message = "Invalid request body. Expected: {\"action\": \"approve\"|\"block\"}"})
        return
    end
    
    local action = request.action
    if action ~= "approve" and action ~= "block" then
        luci.http.status(400, "Bad Request")
        luci.http.prepare_content("application/json")
        luci.http.write_json({success = false, message = "Action must be 'approve' or 'block'"})
        return
    end
    
    -- Load current pending data
    local file_path = get_pending_file_path()
    local content = fs.readfile(file_path)
    local data = {}
    
    if content and content ~= "" then
        local parse_success, parsed = pcall(jsonc.parse, content)
        if parse_success and parsed then
            data = parsed
        end
    end
    
    -- Check if MAC exists in pending list
    if not data[mac] then
        luci.http.status(404, "Not Found")
        luci.http.prepare_content("application/json")
        luci.http.write_json({success = false, message = "MAC address not found in pending list"})
        return
    end
    
    -- Update status
    data[mac].status = action
    data[mac].updated_at = os.date("!%Y-%m-%dT%H:%M:%SZ")
    
    -- Jika approved, set approved_at timestamp
    if action == "approve" then
        data[mac].approved_at = data[mac].updated_at
    elseif action == "block" then
        data[mac].blocked_at = data[mac].updated_at
    end
    
    -- Write back to file (atomic write dengan temp file + rename)
    local temp_file = file_path .. ".tmp." .. os.time()
    local json_str = jsonc.stringify(data, true)
    
    local write_success = fs.writefile(temp_file, json_str)
    if not write_success then
        luci.http.status(500, "Internal Server Error")
        luci.http.prepare_content("application/json")
        luci.http.write_json({success = false, message = "Failed to write pending file"})
        return
    end
    
    -- Atomic rename
    fs.rename(temp_file, file_path)
    
    -- Trigger action ke fas_server.py / pi4Bot.py via script bridge
    -- Script ini akan update status di JSON file + handle whitelist/block via iptables
    local action_script = "/usr/bin/remotbot_actions.py"
    if fs.access(action_script) then
        os.execute(string.format("%s %s %s >/dev/null 2>&1 &", action_script, mac, action))
    end
    
    -- Return success
    luci.http.prepare_content("application/json")
    luci.http.write_json({
        success = true,
        message = "Device " .. action .. "d successfully",
        mac = mac,
        new_status = action
    })
end
