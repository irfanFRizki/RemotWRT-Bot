'use strict';
'require view';
'require poll';
'require rpc';
'require uci';
'require ui';
'require fs';

var callServiceList = rpc.declare({
    object: 'service', method: 'list', params: ['name'], expect: { '': {} }
});

function renderCard(title, icon, content) {
    return E('div', { 'style': 'background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08);' }, [
        E('div', { 'style': 'display:flex;align-items:center;margin-bottom:12px;' }, [
            E('span', { 'style': 'font-size:22px;margin-right:10px;' }, icon),
            E('h3', { 'style': 'margin:0;font-size:16px;color:#333;font-weight:600;' }, title)
        ]),
        content
    ]);
}

function renderRow(label, value, valueStyle) {
    return E('div', { 'style': 'display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #f0f0f0;' }, [
        E('span', { 'style': 'color:#666;font-size:13px;' }, label),
        E('span', { 'style': 'font-weight:600;font-size:13px;' + (valueStyle || '') }, value)
    ]);
}

return view.extend({
    load: function() {
        return Promise.all([ uci.load('remotbot'), callServiceList('remotbot') ]);
    },
    pollData: function(container) {
        return Promise.all([ callServiceList('remotbot'), uci.load('remotbot') ]).then(function(data) {
            var running = data[0] && data[0].remotbot && Object.keys(data[0].remotbot.instances || {}).length > 0;
            var badge = container.querySelector('#status-badge');
            if (badge) { badge.className='label '+(running?'label-success':'label-danger'); badge.textContent=running?'● Running':'● Stopped'; }
            var token = uci.get('remotbot','main','bot_token')||'';
            var el = container.querySelector('#token-display');
            if (el) { el.textContent=token?token.substring(0,8)+'••••••••••••'+token.slice(-4):'Not configured'; el.style.color=token?'#27ae60':'#e74c3c'; }
            var en = container.querySelector('#enabled-display');
            if (en) { var e=uci.get('remotbot','main','enabled')==='1'; en.textContent=e?'Yes':'No'; en.style.color=e?'#27ae60':'#e74c3c'; }
        });
    },
    handleAction: function(action) {
        return fs.exec('/etc/init.d/remotbot',[action]).then(function(res) {
            ui.addNotification(null, E('p', action+': '+(res.code===0?'OK':res.stderr||'error')), res.code===0?'info':'error');
        });
    },
    render: function(data) {
        var svc=data[1]; var running=svc&&svc.remotbot&&Object.keys(svc.remotbot.instances||{}).length>0;
        var token=uci.get('remotbot','main','bot_token')||'';
        var users=uci.get('remotbot','main','allowed_users')||'';
        var enabled=uci.get('remotbot','main','enabled')==='1';
        var cgi=uci.get('remotbot','main','cgi_online_path')||'/www/cgi-bin/online';
        var badge=E('span',{'id':'status-badge','class':'label '+(running?'label-success':'label-danger'),'style':'padding:4px 12px;border-radius:12px;font-size:13px;font-weight:bold;'},running?'● Running':'● Stopped');
        var container=E('div',{'style':'max-width:900px;margin:0 auto;padding:16px;'},[
            E('div',{'style':'background:linear-gradient(135deg,#2c3e50,#3498db);border-radius:10px;padding:20px 24px;margin-bottom:20px;color:#fff;display:flex;justify-content:space-between;align-items:center;'},[
                E('div',{},[E('h2',{'style':'margin:0 0 4px;'},'🤖 RemotWRT Bot'),E('p',{'style':'margin:0;opacity:.85;font-size:14px;'},'Telegram Monitoring Bot — OpenWrt / Raspberry Pi 4')]),badge]),
            renderCard('Status','📊',E('div',{},[
                renderRow('Service',running?'● Running':'● Stopped',running?'color:#27ae60':'color:#e74c3c'),
                renderRow('Auto-Start',enabled?'Yes':'No',enabled?'color:#27ae60':'color:#e74c3c'),
                E('div',{'style':'display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;'},[E('span',{'style':'color:#666;font-size:13px;'},'Bot Token'),E('span',{'id':'token-display','style':'font-weight:600;font-size:13px;font-family:monospace;color:'+(token?'#27ae60':'#e74c3c')+';'},token?token.substring(0,8)+'••••••••••••'+token.slice(-4):'Not configured')]),
                renderRow('Allowed Users',users||'Not configured'),
                renderRow('CGI Path',cgi),
            ])),
            renderCard('Service Control','⚙️',E('div',{'style':'display:flex;gap:10px;flex-wrap:wrap;'},[
                E('button',{'class':'btn cbi-button cbi-button-positive','style':'min-width:90px;','click':ui.createHandlerFn(this,function(){return this.handleAction('start');})},'▶ Start'),
                E('button',{'class':'btn cbi-button cbi-button-negative','style':'min-width:90px;','click':ui.createHandlerFn(this,function(){return this.handleAction('stop');})},'■ Stop'),
                E('button',{'class':'btn cbi-button cbi-button-action','style':'min-width:90px;','click':ui.createHandlerFn(this,function(){return this.handleAction('restart');})},'↺ Restart'),
                E('button',{'class':'btn cbi-button','style':'min-width:90px;','click':function(){window.location.href='/cgi-bin/luci/admin/services/remotbot/settings';}},'⚙ Settings'),
            ])),
            !token?renderCard('Quick Setup','🚀',E('div',{},[
                E('p',{'style':'color:#e74c3c;font-weight:bold;margin-top:0;'},'⚠️ Bot token belum dikonfigurasi!'),
                E('ol',{'style':'margin:0;padding-left:20px;line-height:2;'},[
                    E('li',{},'Buat bot via @BotFather → copy token'),
                    E('li',{},[' Buka ',E('a',{href:'/cgi-bin/luci/admin/services/remotbot/settings'},'Settings'),' → paste token']),
                    E('li',{},'Dapat User ID via @userinfobot'),
                    E('li',{},'Masukkan User ID ke Allowed Users'),
                    E('li',{},'Enable bot → klik Start'),
                ])
            ])):E('span'),
            renderCard('Info','ℹ️',E('div',{},[
                renderRow('Package','remotbot v1.0.0'),
                renderRow('Script','/usr/bin/pi4Bot.py'),
                renderRow('Config','/etc/config/remotbot'),
                renderRow('PID','/var/run/remotbot.pid'),
            ])),
        ]);
        poll.add(L.bind(this.pollData,this,container),5);
        return container;
    },
    handleSaveApply:null, handleSave:null, handleReset:null
});
