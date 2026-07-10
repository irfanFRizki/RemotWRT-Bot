local m, s

m = Map("remotwrt", "Voucher Manager", "Manage WiFi vouchers for family and guest users")

-- Generate Voucher Section
s = m:section(NamedSection, "generate", "voucher_gen", "Generate New Voucher")
s.anonymous = true

category = s:option(ListValue, "category", "Category")
category:value("keluarga", "Keluarga")
category:value("pengguna_lain", "Pengguna Lain")

validity = s:option(Value, "validity", "Validity (minutes)")
validity.datatype = "uinteger"
validity.default = "60"

max_use = s:option(Value, "max_use", "Max Usage")
max_use.datatype = "uinteger"
max_use.default = "1"

permanent = s:option(Flag, "permanent", "Permanent Access (No Expiry)")
permanent.default = 0
permanent.description = "Only applicable for Keluarga category. Guest vouchers always expire."

btn_generate = s:option(Button, "_generate", "Generate")
btn_generate.inputtitle = "Generate Voucher"
btn_generate.write = function()
    -- Generation logic handled by controller
end

-- Active Vouchers List
s = m:section(TypedSection, "voucher", "Active Vouchers")
s.anonymous = false
s.addremove = true
s.template_addremove = "remotwrt/voucher_addremove"

code = s:option(Value, "code", "Voucher Code")
code.rmempty = false

cat = s:option(ListValue, "category", "Category")
cat:value("keluarga", "Keluarga")
cat:value("pengguna_lain", "Pengguna Lain")

valid = s:option(Value, "validity", "Validity (min)")
valid.datatype = "uinteger"

perm = s:option(Flag, "permanent", "Permanent")
perm.default = 0
perm.readonly = true

uses_opt = s:option(DummyValue, "uses", "Times Used")
uses_opt.default = "0"

created_opt = s:option(DummyValue, "created", "Created At")
created_opt.rawhtml = true
created_opt.render = function(self, section, scope)
    local created = scope.ctldata[section].created or "0"
    if created == "0" then
        self.value = "N/A"
    else
        self.value = os.date("%Y-%m-%d %H:%M", tonumber(created))
    end
    DummyValue.render(self, section, scope)
end

max_use_display = s:option(DummyValue, "max_use", "Max Use")
max_use_display.default = "1"

status = s:option(Flag, "status", "Status")
status.default = 1
status.readonly = true

return m
