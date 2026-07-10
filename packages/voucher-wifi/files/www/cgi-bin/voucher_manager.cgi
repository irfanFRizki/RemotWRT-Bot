#!/bin/sh
# Voucher Manager CGI untuk LuCI
# Lokasi: /www/cgi-bin/voucher_manager.cgi

echo "Content-type: text/html"
echo ""

# Load UCI Lua library
lua << 'LUA_SCRIPT'
local uci = require("uci")
local fs = require("nixio.fs")
local http = require("luci.http")

-- Helper function untuk escape HTML
function html_escape(str)
    if not str then return "" end
    return string.gsub(str, "[<>&\"]", {
        ["<"] = "&lt;",
        [">"] = "&gt;",
        ["&"] = "&amp;",
        ['"'] = "&quot;"
    })
end

-- Baca action dari form
local action = http.formvalue("action")
local category = http.formvalue("category")
local voucher_code = http.formvalue("voucher_code")
local ip_address = http.formvalue("ip_address")

-- Inisialisasi cursor UCI
local cursor = uci.cursor()

-- Fungsi untuk membaca daftar voucher keluarga
function get_keluarga_vouchers()
    local vouchers = {}
    local file = io.open("/etc/voucher_keluarga.txt", "r")
    if file then
        for line in file:lines() do
            if line and line ~= "" then
                table.insert(vouchers, line)
            end
        end
        file:close()
    end
    return vouchers
end

-- Fungsi untuk membaca IP whitelist dari firewall
function get_firewall_whitelist()
    local ips = {}
    
    -- Baca dari config firewall OpenWRT
    cursor:foreach("firewall", "zone", function(section)
        if section.name == "trusted" or section.input == "ACCEPT" then
            -- Cari rule yang spesifik untuk IP
            cursor:foreach("firewall", "rule", function(rule)
                if rule.target == "ACCEPT" and rule.src_ip then
                    table.insert(ips, rule.src_ip)
                end
            end)
        end
    end)
    
    -- Juga baca dari iptables langsung (fallback)
    local f = io.popen("iptables -L FORWARD -n -v | grep ACCEPT | awk '{print $8}' | cut -d'/' -f1 | sort -u")
    if f then
        for line in f:lines() do
            if line and line ~= "" and line:match("%d+%.%d+%.%d+%.%d+") then
                table.insert(ips, line)
            end
        end
        f:close()
    end
    
    return ips
end

-- Proses aksi
if action == "add_voucher" then
    if category == "keluarga" and voucher_code and voucher_code ~= "" then
        -- Tambahkan voucher ke file
        local file = io.open("/etc/voucher_keluarga.txt", "a")
        if file then
            file:write(voucher_code .. "\n")
            file:close()
        end
    elseif category == "whitelist_ip" and ip_address and ip_address ~= "" then
        -- Tambahkan IP ke firewall whitelist
        os.execute(string.format("iptables -I FORWARD 1 -s %s -j ACCEPT", ip_address))
        
        -- Simpan ke config firewall agar persisten
        local idx = cursor:add("firewall", "rule")
        cursor:set("firewall", idx, "target", "ACCEPT")
        cursor:set("firewall", idx, "src_ip", ip_address)
        cursor:set("firewall", idx, "proto", "all")
        cursor:set("firewall", idx, "name", "Whitelist_" .. ip_address:gsub("%.", "_"))
        cursor:save("firewall")
    end
elseif action == "delete_voucher" then
    if voucher_code then
        -- Hapus voucher dari file
        local temp_file = "/tmp/voucher_temp.txt"
        os.execute(string.format("grep -v '^%s$' /etc/voucher_keluarga.txt > %s", voucher_code, temp_file))
        os.execute(string.format("mv %s /etc/voucher_keluarga.txt", temp_file))
    end
elseif action == "remove_ip" then
    if ip_address then
        -- Hapus IP dari iptables
        os.execute(string.format("iptables -D FORWARD -s %s -j ACCEPT 2>/dev/null", ip_address))
        
        -- Hapus dari config firewall
        cursor:foreach("firewall", "rule", function(rule)
            if rule.src_ip == ip_address then
                cursor:delete("firewall", rule[".name"])
            end
        end)
        cursor:save("firewall")
    end
end

-- Generate HTML
local keluarga_vouchers = get_keluarga_vouchers()
local whitelist_ips = get_firewall_whitelist()

?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voucher Manager - RemotWRT</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        .card {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h2 {
            color: #667eea;
            margin-top: 0;
            font-size: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #555;
        }
        input[type="text"], select {
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            box-sizing: border-box;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 5px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
        }
        button.danger {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #667eea;
            color: white;
        }
        tr:hover {
            background: #f5f5f5;
        }
        .badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-success {
            background: #d4edda;
            color: #155724;
        }
        .badge-info {
            background: #d1ecf1;
            color: #0c5460;
        }
        .alert {
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border-left: 4px solid #17a2b8;
        }
        .no-data {
            text-align: center;
            color: #999;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎫 Voucher WiFi Manager</h1>
        
        <div class="alert alert-info">
            <strong>ℹ️ Info:</strong> 
            IP yang ada di Firewall Whitelist akan otomatis mendapatkan akses internet tanpa perlu login voucher.
        </div>

        <!-- Form Tambah Voucher -->
        <div class="card">
            <h2>➕ Tambah Voucher Keluarga</h2>
            <form method="post">
                <input type="hidden" name="action" value="add_voucher">
                <div class="form-group">
                    <label>Kategori:</label>
                    <select name="category" required>
                        <option value="keluarga">Keluarga</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Kode Voucher:</label>
                    <input type="text" name="voucher_code" placeholder="Contoh: KELUARGA123" required>
                </div>
                <button type="submit">Tambah Voucher</button>
            </form>
        </div>

        <!-- Form Tambah IP Whitelist -->
        <div class="card">
            <h2>🔒 Tambah IP ke Firewall Whitelist</h2>
            <form method="post">
                <input type="hidden" name="action" value="whitelist_ip">
                <div class="form-group">
                    <label>Alamat IP:</label>
                    <input type="text" name="ip_address" placeholder="Contoh: 192.168.1.100" pattern="\\d+\\.\\d+\\.\\d+\\.\\d+" required>
                    <small style="color: #666;">IP ini akan langsung bisa internet tanpa login voucher</small>
                </div>
                <button type="submit">Tambah ke Whitelist</button>
            </form>
        </div>

        <!-- Daftar Voucher -->
        <div class="card">
            <h2>📋 Daftar Voucher Keluarga Aktif</h2>
            <? if #keluarga_vouchers > 0 then ?>
            <table>
                <thead>
                    <tr>
                        <th>No</th>
                        <th>Kode Voucher</th>
                        <th>Aksi</th>
                    </tr>
                </thead>
                <tbody>
                    <? 
                    for i, voucher in ipairs(keluarga_vouchers) do 
                    ?>
                    <tr>
                        <td><?=i?></td>
                        <td><span class="badge badge-success"><?=html_escape(voucher)?></span></td>
                        <td>
                            <form method="post" style="display:inline;">
                                <input type="hidden" name="action" value="delete_voucher">
                                <input type="hidden" name="voucher_code" value="<?=html_escape(voucher)?>">
                                <button type="submit" class="danger" style="padding: 5px 10px; font-size: 12px;">Hapus</button>
                            </form>
                        </td>
                    </tr>
                    <? end ?>
                </tbody>
            </table>
            <? else ?>
            <div class="no-data">Belum ada voucher keluarga</div>
            <? end ?>
        </div>

        <!-- Daftar IP Whitelist -->
        <div class="card">
            <h2>🛡️ IP Firewall Whitelist (Auto Access)</h2>
            <? if #whitelist_ips > 0 then ?>
            <table>
                <thead>
                    <tr>
                        <th>No</th>
                        <th>Alamat IP</th>
                        <th>Status</th>
                        <th>Aksi</th>
                    </tr>
                </thead>
                <tbody>
                    <? 
                    local seen = {}
                    local count = 0
                    for i, ip in ipairs(whitelist_ips) do 
                        if not seen[ip] then
                            seen[ip] = true
                            count = count + 1
                    ?>
                    <tr>
                        <td><?=count?></td>
                        <td><span class="badge badge-info"><?=html_escape(ip)?></span></td>
                        <td>Otomatis Login</td>
                        <td>
                            <form method="post" style="display:inline;">
                                <input type="hidden" name="action" value="remove_ip">
                                <input type="hidden" name="ip_address" value="<?=html_escape(ip)?>">
                                <button type="submit" class="danger" style="padding: 5px 10px; font-size: 12px;">Hapus</button>
                            </form>
                        </td>
                    </tr>
                    <? end end ?>
                </tbody>
            </table>
            <? else ?>
            <div class="no-data">Belum ada IP di whitelist firewall</div>
            <? end ?>
        </div>
    </div>
</body>
</html>
LUA_SCRIPT
