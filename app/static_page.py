WEB_PAGE_HTML = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Na7la Powerat 🐝⚡ نحلة باورات</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card: #151c2c;
      --card-border: #1e293b;
      --primary: #3b82f6;
      --success: #10b981;
      --danger: #ef4444;
      --text: #f8fafc;
      --text-dim: #94a3b8;
      --btn-off: #1e293b;
      --btn-on: #059669;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Cairo', sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 20px; max-width: 820px; margin: auto; }
    header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--card-border); }
    h1 { font-size: 24px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
    .badge { background: #1e3a8a; color: #93c5fd; font-size: 12px; padding: 4px 10px; border-radius: 20px; }
    .server-info { background: var(--card); border: 1px solid var(--card-border); padding: 12px 16px; border-radius: 12px; font-size: 13px; color: var(--text-dim); margin-bottom: 20px; display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; }
    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 16px; padding: 20px; margin-bottom: 20px; transition: 0.2s ease; }
    .card.offline { opacity: 0.6; filter: grayscale(0.5); }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
    .device-title { font-size: 18px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
    .status-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--danger); display: inline-block; }
    .status-dot.online { background: var(--success); box-shadow: 0 0 10px var(--success); }
    .metrics-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 20px; }
    .metric-pill { background: #0f172a; border: 1px solid #1e293b; padding: 10px; border-radius: 10px; text-align: center; }
    .metric-label { font-size: 11px; color: var(--text-dim); }
    .metric-value { font-size: 16px; font-weight: 700; color: #38bdf8; }
    .outlets-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    @media (max-width: 600px) { .outlets-grid { grid-template-columns: 1fr; } }
    .outlet-btn { background: var(--btn-off); border: 1px solid var(--card-border); border-radius: 12px; padding: 16px; color: var(--text); cursor: pointer; text-align: right; transition: all 0.2s; display: flex; justify-content: space-between; align-items: center; }
    .outlet-btn:hover { border-color: var(--primary); }
    .outlet-btn.on { background: #064e3b; border-color: #059669; }
    .outlet-name { font-weight: 700; font-size: 15px; }
    .outlet-sub { font-size: 12px; color: var(--text-dim); margin-top: 4px; }
    .master-btn { background: var(--primary); color: #fff; border: 0; padding: 10px 18px; border-radius: 10px; font-weight: 700; cursor: pointer; }
    .master-btn.all-off { background: #dc2626; }
    .links-bar { display: flex; gap: 10px; margin-top: 15px; font-size: 13px; }
    .links-bar a { color: #38bdf8; text-decoration: none; }
  </style>
</head>
<body>
  <header>
    <h1>🐝⚡ Na7la Powerat <span class="badge">نحلة باورات</span></h1>
    <a href="https://t.me/Na7laPoweratBot" target="_blank" class="master-btn" style="background:#0284c7;text-decoration:none">🤖 فتح بوت تليجرام</a>
  </header>

  <div class="server-info" id="serverInfo">
    <span>جاري الاتصال بالخادم...</span>
  </div>

  <div id="devicesContainer"></div>

  <div class="links-bar">
    <a href="/docs" target="_blank">📖 Swagger API Docs</a> · 
    <a href="/powerk.apk">📱 تطبيق أندرويد APK</a> · 
    <a href="https://github.com/hassanaref/powerk" target="_blank">GitHub Repo</a>
  </div>

  <script>
    const api = async (p, b) => {
      const opts = b ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) } : {};
      const res = await fetch(p, opts);
      return res.json();
    };

    async function toggleOutlet(mac, outlet, on) {
      await api('/api/onoff', { mac, outlet, on });
      await refresh();
    }

    function render(data) {
      const sInfo = document.getElementById('serverInfo');
      sInfo.innerHTML = `
        <div><strong>عنوان الخادم:</strong> ${data.local_ip || '127.0.0.1'} | <strong>منفذ المشترك:</strong> TCP ${data.port}</div>
        <div><strong>التليجرام:</strong> @Na7laPoweratBot</div>
      `;

      const container = document.getElementById('devicesContainer');
      if (!data.devices || data.devices.length === 0) {
        container.innerHTML = `
          <div class="card" style="text-align:center;padding:40px 20px;">
            <h3>لا يوجد مشترك متصل حالياً</h3>
            <p style="color:var(--text-dim);margin-top:10px;">قم بتوصيل المشترك بالكهرباء والواي فاي، وسيتصل تلقائياً بالمنفذ 10086.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = data.devices.map(d => `
        <div class="card ${d.online ? '' : 'offline'}">
          <div class="card-header">
            <div class="device-title">
              <span class="status-dot ${d.online ? 'online' : ''}"></span>
              ${d.name} (${d.mac.slice(-4)})
            </div>
            <button class="master-btn ${d.on ? 'all-off' : ''}" onclick="toggleOutlet('${d.mac}', 0, ${!d.on})">
              ${d.on ? '🛑 إيقاف الكل' : '⚡ تشغيل الكل'}
            </button>
          </div>

          <div class="metrics-bar">
            <div class="metric-pill">
              <div class="metric-label">القدرة اللحظية</div>
              <div class="metric-value">${d.power_w} W</div>
            </div>
            <div class="metric-pill">
              <div class="metric-label">الطاقة الكلية</div>
              <div class="metric-value">${d.energy_kwh} kWh</div>
            </div>
            <div class="metric-pill">
              <div class="metric-label">الجهد</div>
              <div class="metric-value">${d.voltage ? d.voltage + ' V' : '--'}</div>
            </div>
            <div class="metric-pill">
              <div class="metric-label">التيار الإجمالي</div>
              <div class="metric-value">${d.current_a ? d.current_a + ' A' : '--'}</div>
            </div>
            <div class="metric-pill">
              <div class="metric-label">إشارة الواي فاي</div>
              <div class="metric-value">${d.rssi ? d.rssi + ' dBm' : '--'}</div>
            </div>
          </div>

          <div class="outlets-grid">
            ${d.outlets.map(o => `
              <div class="outlet-btn ${o.on ? 'on' : ''}" onclick="toggleOutlet('${d.mac}', ${o.channel || o.n}, ${!o.on})">
                <div>
                  <div class="outlet-name">${o.channel || o.n}. ${o.name || 'المخرج ' + (o.channel || o.n)}</div>
                  <div class="outlet-sub">${o.power_w} W · ${o.temp_c || 0}°C</div>
                </div>
                <div style="font-size:20px;">${o.on ? '🟢' : '⚪'}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `).join('');
    }

    async function refresh() {
      try {
        const data = await api('/api/state');
        render(data);
      } catch (err) {
        console.error("Refresh error:", err);
      }
    }

    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
"""
