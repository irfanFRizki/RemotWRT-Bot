# luci-app-remotwrt

Advanced WiFi Management Application for OpenWrt with LuCI interface. Provides real-time device monitoring, voucher-based authentication, firewall management, and comprehensive network statistics.

## Features

### 📊 Dashboard
- **Real-time Device Monitoring**: View all connected devices with IP, MAC, status, and source
- **Network Statistics**: Total devices, authenticated users, pending connections, whitelisted devices
- **Quick Actions**: Generate vouchers, manage firewall rules directly from dashboard

### 🔐 Voucher System
- **Category-based Vouchers**: 
  - Keluarga (Family) - Extended validity
  - Pengguna Lain (Guest) - Limited access with custom message
- **Voucher Generation**: Auto-generate unique codes with configurable validity
- **MAC/IP Binding**: Bind vouchers to specific devices
- **Usage Tracking**: Monitor voucher usage and expiration

### 🛡️ Firewall Management
- **Whitelist**: Allow specific devices to bypass authentication
- **Blacklist**: Block unwanted devices from network access
- **Rule Management**: Add/remove rules via LuCI interface
- **Auto-detection**: Quickly whitelist detected devices

### 📈 Device History
- **Connection Logs**: Track all devices that have connected
- **Event Timeline**: Timestamp, MAC, IP, and event type
- **Search & Filter**: Find specific devices in history
- **Export Capability**: Download history data

### ⚙️ Network Settings
- **LAN Configuration**: Set IP address, gateway, DNS
- **Portal Settings**: Configure redirect URLs, session timeout
- **Voucher Defaults**: Set default validity periods
- **Guest Network**: Enable/disable guest access

## Installation

### Prerequisites
- OpenWrt router with LuCI installed
- OpenNDS package installed (`opkg install opennds`)
- Sufficient storage space (~500KB)

### Build from Source

```bash
# Clone OpenWrt buildroot
git clone https://git.openwrt.org/openwrt/openwrt.git
cd openwrt

# Copy package to feeds
cp -r luci-app-remotwrt package/luci-app-remotwrt

# Update feeds
./scripts/feeds update -a
./scripts/feeds install -a

# Select package
make menuconfig
# Navigate to: LuCI -> Applications -> luci-app-remotwrt

# Build package
make package/luci-app-remotwrt/compile V=s
```

### Install Pre-built Package

```bash
# Upload to router
scp luci-app-remotwrt_1.0.0-1_all.ipk root@192.168.1.1:/tmp/

# SSH to router
ssh root@192.168.1.1

# Install
opkg install /tmp/luci-app-remotwrt_1.0.0-1_all.ipk

# Enable service
/etc/init.d/remotwrt enable
/etc/init.d/remotwrt start
```

## Usage

### Accessing the Interface

1. Log in to LuCI web interface (http://192.168.1.1)
2. Navigate to **Services** → **RemotWRT WiFi**
3. Access sub-menus:
   - **Dashboard**: Real-time monitoring
   - **Voucher Manager**: Generate and manage vouchers
   - **Firewall Rules**: Whitelist/blacklist management
   - **Settings**: Network configuration
   - **Device History**: Connection logs

### Creating Your First Voucher

1. Go to **Services** → **RemotWRT WiFi** → **Voucher Manager**
2. Click **Add** under Active Vouchers
3. Enter:
   - **Voucher Code**: e.g., `FAMILY123`
   - **Category**: Choose "Keluarga" or "Pengguna Lain"
   - **Validity**: Duration in minutes
   - **Status**: Enable
4. Save & Apply

### Whitelisting a Device

**Method 1: From Dashboard**
1. Go to **Dashboard**
2. Find device in Connected Devices list
3. Click **Whitelist** button
4. Confirm action

**Method 2: From Firewall Rules**
1. Go to **Firewall Rules** → **Whitelist**
2. Click **Add**
3. Enter MAC address (required) and IP (optional)
4. Add description for reference
5. Save & Apply

### Viewing Device History

1. Navigate to **Device History**
2. View chronological list of connections
3. Use **Refresh** to update
4. Use **Clear History** to reset logs

## Configuration Files

### Main Configuration
Location: `/etc/config/remotwrt`

```config
config remotwrt 'main'
    option enabled '1'
    option login_redirect_url 'http://192.168.1.1:8080'
    option voucher_validity '60'
    option max_devices '10'

config voucher 'example'
    option code 'VOUCHER123'
    option category 'keluarga'
    option validity '1440'
    option status 'active'

config firewall_whitelist 'admin_device'
    option mac 'AA:BB:CC:DD:EE:FF'
    option ip '192.168.1.100'
    option description 'Admin Laptop'
    option enabled '1'
```

### Log Files
- **Main Log**: `/var/log/remotwrt.log`
- **Device History**: `/var/lib/remotwrt/device_history.json`
- **State File**: `/var/run/remotwrt.state`

## API Reference

### Get Connected Devices
```bash
curl -X POST http://192.168.1.1/cgi-bin/luci/admin/services/remotwrt/api \
  -d "action=get_devices"
```

Response:
```json
[
  {
    "ip": "192.168.1.50",
    "mac": "AA:BB:CC:DD:EE:FF",
    "status": "authenticated",
    "source": "opennds"
  }
]
```

### Generate Voucher
```bash
curl -X POST http://192.168.1.1/cgi-bin/luci/admin/services/remotwrt/api \
  -d "action=generate_voucher&category=keluarga&validity=120"
```

### Add Firewall Rule
```bash
curl -X POST http://192.168.1.1/cgi-bin/luci/admin/services/remotwrt/api \
  -d "action=add_firewall_rule&rule_type=whitelist&mac=AA:BB:CC:DD:EE:FF&ip=192.168.1.50"
```

## Troubleshooting

### Package Won't Install
```bash
# Check dependencies
opkg list | grep opennds
opkg install opennds

# Check disk space
df -h

# Force install
opkg install --force-depends /tmp/luci-app-remotwrt.ipk
```

### LuCI Interface Not Showing
```bash
# Clear LuCI cache
rm -rf /tmp/luci-*
/etc/init.d/uhttpd restart

# Check file permissions
chmod 755 /usr/lib/lua/luci/controller/remotwrt.lua
```

### Devices Not Appearing in Dashboard
```bash
# Check OpenNDS status
ndsctl status

# Restart monitor service
/etc/init.d/remotwrt restart

# Check logs
logread | grep remotwrt
cat /var/log/remotwrt.log
```

### Voucher Authentication Fails
```bash
# Verify voucher exists in config
uci show remotwrt | grep voucher

# Check OpenNDS configuration
cat /etc/config/opennds

# Test authentication script manually
/usr/bin/voucher_auth.sh
```

## Development

### Project Structure
```
luci-app-remotwrt/
├── Makefile
├── files/
│   ├── etc/
│   │   ├── config/remotwrt
│   │   └── init.d/remotwrt
│   ├── usr/
│   │   ├── bin/remotwrt_monitor.sh
│   │   └── share/rpcd/acl.d/luci-app-remotwrt.json
│   └── www/
└── root/
    └── usr/lib/lua/luci/
        ├── controller/remotwrt.lua
        ├── model/cbi/remotwrt/
        │   ├── vouchers.lua
        │   ├── firewall.lua
        │   └── settings.lua
        └── view/remotwrt/
            ├── dashboard.htm
            └── history.htm
```

### Adding New Features
1. Create Lua controller in `controller/`
2. Add CBI model in `model/cbi/remotwrt/`
3. Create view template in `view/remotwrt/`
4. Update `Makefile` if adding dependencies
5. Test in development environment

## License

Apache License 2.0

## Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## Support

For issues and feature requests, please open an issue on GitHub.

---

**Note**: This package requires OpenWrt 21.02 or later with LuCI installed.
