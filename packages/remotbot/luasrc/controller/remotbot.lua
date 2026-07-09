module("luci.controller.remotbot", package.seeall)

function index()
    -- Halaman utama menu RemotWRT-Bot
    entry({"admin", "services", "remotbot"}, alias("admin", "services", "remotbot", "pending"), _("RemotWRT-Bot"), 10).dependent = true
    
    -- Halaman daftar pending approval OpenNDS
    entry({"admin", "services", "remotbot", "pending"}, template("remotbot/pending_list"), _("Pending Approval"), 10)
    
    -- Halaman konfigurasi (reuse yang sudah ada jika ada, atau buat baru)
    entry({"admin", "services", "remotbot", "config"}, cbi("remotbot/config"), _("Configuration"), 20)
end
