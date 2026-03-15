'use strict';
'require view';
'require form';
'require uci';
'require ui';
'require fs';

return view.extend({
    load: function() { return uci.load('remotbot'); },
    render: function() {
        var m, s, o;
        m = new form.Map('remotbot', _('Remot Bot — Settings'), _('Konfigurasi Telegram Bot Token dan pengaturan lainnya.'));
        s = m.section(form.NamedSection, 'main', 'remotbot', _('Bot Configuration'));
        s.anonymous = false; s.addremove = false;

        o = s.option(form.Flag, 'enabled', _('Enable Bot'), _('Aktifkan auto-start saat boot.'));
        o.default = '0'; o.rmempty = false;

        o = s.option(form.Value, 'bot_token', _('Telegram Bot Token'), _('Buat bot via <a href="https://t.me/BotFather" target="_blank">@BotFather</a>.'));
        o.password = true; o.placeholder = '1234567890:AAECVsHH...'; o.rmempty = false;
        o.validate = function(sid, val) {
            if (!val||val.trim()==='') return _('Token wajib diisi');
            if (!/^\d+:[A-Za-z0-9_-]{30,50}$/.test(val.trim())) return _('Format tidak valid');
            return true;
        };

        o = s.option(form.Value, 'allowed_users', _('Allowed Telegram User IDs'), _('Pisahkan dengan spasi. Cari via <a href="https://t.me/userinfobot" target="_blank">@userinfobot</a>.'));
        o.placeholder = '5645537022 1234567890'; o.rmempty = false;
        o.validate = function(sid, val) {
            if (!val||val.trim()==='') return _('Minimal satu User ID');
            var ids=val.trim().split(/[\s,]+/);
            for (var i=0;i<ids.length;i++) { if (ids[i]&&!/^\d+$/.test(ids[i])) return _('User ID tidak valid: '+ids[i]); }
            return true;
        };

        o = s.option(form.Value, 'cgi_online_path', _('CGI Online Users Path'));
        o.default = '/www/cgi-bin/online'; o.placeholder = '/www/cgi-bin/online';

        o = s.option(form.ListValue, 'log_level', _('Log Level'));
        o.value('DEBUG','DEBUG'); o.value('INFO','INFO'); o.value('WARNING','WARNING'); o.value('ERROR','ERROR');
        o.default = 'INFO';

        s = m.section(form.NamedSection, 'main', 'remotbot', _('Test Token'));
        s.anonymous = false; s.addremove = false;
        o = s.option(form.DummyValue, '_test', _('Verifikasi Token'));
        o.rawhtml = true; o.write = function() {};
        o.cfgvalue = function() {
            return '<button class="btn cbi-button cbi-button-positive" onclick="testToken(event)">✓ Test Token</button>' +
                   '<span id="test-result" style="margin-left:12px;font-size:13px;"></span>';
        };

        return m.render().then(function(node) {
            var sc=document.createElement('script');
            sc.textContent='function testToken(e){e.preventDefault();var el=document.querySelector("input[id*=\'bot_token\']");var tok=el?el.value:"";var res=document.getElementById("test-result");if(!tok){res.textContent="Isi token dulu";res.style.color="#e74c3c";return;}res.textContent="Mengecek...";res.style.color="#f39c12";fetch("https://api.telegram.org/bot"+tok+"/getMe").then(function(r){return r.json();}).then(function(d){if(d.ok){res.textContent="✓ Valid! Bot: @"+d.result.username;res.style.color="#27ae60";}else{res.textContent="✗ "+d.description;res.style.color="#e74c3c";}}).catch(function(){res.textContent="Network error";res.style.color="#e74c3c";});}';
            node.appendChild(sc); return node;
        });
    }
});
