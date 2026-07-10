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

status = s:option(Flag, "status", "Status")
status.default = 1

return m
