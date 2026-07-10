local m, s

m = Map("remotwrt", "Firewall Rules", "Manage whitelist and blacklist for MAC/IP addresses")

-- Whitelist Section
s = m:section(TypedSection, "firewall_whitelist", "Whitelist (Allowed Devices)", 
    "Devices in this list can access internet without voucher authentication")
s.anonymous = false
s.addremove = true

ip_wl = s:option(Value, "ip", "IP Address")
ip_wl.datatype = "ip4addr"
ip_wl.rmempty = true

mac_wl = s:option(Value, "mac", "MAC Address")
mac_wl.datatype = "macaddr"
mac_wl.rmempty = false

desc_wl = s:option(Value, "description", "Description")
desc_wl.rmempty = true

enabled_wl = s:option(Flag, "enabled", "Enabled")
enabled_wl.default = 1

-- Blacklist Section
s = m:section(TypedSection, "firewall_blacklist", "Blacklist (Blocked Devices)",
    "Devices in this list will be blocked from accessing the network")
s.anonymous = false
s.addremove = true

ip_bl = s:option(Value, "ip", "IP Address")
ip_bl.datatype = "ip4addr"
ip_bl.rmempty = true

mac_bl = s:option(Value, "mac", "MAC Address")
mac_bl.datatype = "macaddr"
mac_bl.rmempty = false

desc_bl = s:option(Value, "description", "Description")
desc_bl.rmempty = true

enabled_bl = s:option(Flag, "enabled", "Enabled")
enabled_bl.default = 1

return m
