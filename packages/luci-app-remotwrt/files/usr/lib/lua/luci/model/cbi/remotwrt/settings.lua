local m, s

m = Map("remotwrt", "RemotWRT Settings", "Configure WiFi portal and network settings")

-- General Settings
s = m:section(TypedSection, "main", "General Settings")
s.anonymous = true

enabled = s:option(Flag, "enabled", "Enable RemotWRT")
enabled.default = 1

redirect_url = s:option(Value, "login_redirect_url", "Login Redirect URL")
redirect_url.datatype = "string"
redirect_url.default = "http://192.168.1.1:8080"
redirect_url.description = "URL where users are redirected after login"

voucher_validity = s:option(Value, "voucher_validity", "Default Voucher Validity (minutes)")
voucher_validity.datatype = "uinteger"
voucher_validity.default = "60"

max_devices = s:option(Value, "max_devices", "Max Concurrent Devices")
max_devices.datatype = "uinteger"
max_devices.default = "10"

guest_enabled = s:option(Flag, "guest_network_enabled", "Enable Guest Network")
guest_enabled.default = 0

whitelist_bypass = s:option(Flag, "whitelist_bypass", "Whitelist Bypass Authentication")
whitelist_bypass.default = 1
whitelist_bypass.description = "Allow whitelisted IPs to access without voucher"

-- Network Settings
s = m:section(TypedSection, "network", "Network Configuration")
s.anonymous = true

lan_ip = s:option(Value, "lan_ip", "LAN IP Address")
lan_ip.datatype = "ip4addr"
lan_ip.default = "192.168.1.1"

gateway = s:option(Value, "gateway", "Gateway")
gateway.datatype = "ip4addr"
gateway.default = "192.168.1.1"

dns_server = s:option(Value, "dns_server", "DNS Server")
dns_server.datatype = "ip4addr"
dns_server.default = "8.8.8.8"

return m
