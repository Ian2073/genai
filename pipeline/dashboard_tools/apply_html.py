import re, sys

with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f: text = f.read()

# 1. Update the root CSS
new_css_root = '''
    :root {
      --bg: #f5f5f5;
      --bg-2: #eeeeee;
      --card: #ffffff;
      --sidebar-bg: #1c1c1e;
      --sidebar-text: #e1e1e1;
      --sidebar-hover: #2c2c2e;
      --sidebar-active: #ffffff;
      --ink: #111827;
      --muted: #6b7280;
      --line: #e5e7eb;
      --accent: #2563eb;
      --accent-strong: #1d4ed8;
      --accent-soft: #eff6ff;
      --ok: #16a34a;
      --warn: #d97706;
      --danger: #dc2626;
      --shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      overflow: hidden; /* Stop main body scrolling */
    }

    .app-layout {
      display: flex;
      width: 100vw;
      height: 100vh;
    }

    /* === SIDEBAR === */
    .sidebar {
      width: 260px;
      background: var(--sidebar-bg);
      color: var(--sidebar-text);
      display: flex;
      flex-direction: column;
      border-right: 1px solid rgba(0,0,0,0.1);
      z-index: 10;
    }

    .brand {
      padding: 24px 20px;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .brand h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      color: #fff;
    }
    .brand p {
      margin: 0 0 4px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #888;
    }

    .nav-menu {
      padding: 16px 12px;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .tab-btn {
      display: flex;
      align-items: center;
      width: 100%;
      background: none;
      border: none;
      padding: 10px 14px;
      font-size: 14px;
      font-weight: 500;
      color: var(--sidebar-text);
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
      text-align: left;
    }
    .tab-btn:hover {
      background: var(--sidebar-hover);
    }
    .tab-btn.active {
      background: rgba(37,99,235,0.15);
      color: #60a5fa;
    }

    .sidebar-footer {
      padding: 20px;
      border-top: 1px solid rgba(255,255,255,0.05);
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .sidebar-footer select, .sidebar-footer input {
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.2);
      color: #fff;
      padding: 4px;
      border-radius: 4px;
      font-size: 12px;
      width: 100%;
    }

    /* === MAIN CONTENT === */
    .main-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      background: var(--bg);
      padding: 32px 48px;
    }

    .main-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
    }

    .hero-kpis {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }
    .hero-kpi {
      background: var(--card);
      padding: 12px 16px;
      border-radius: 8px;
      border: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      min-width: 130px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .hero-kpi b {
      font-size: 11px;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 4px;
    }
    .hero-kpi span {
      font-size: 20px;
      font-weight: 600;
      color: var(--ink);
    }

    .card {
      background: var(--card);
      border-radius: 12px;
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      padding: 24px;
      margin-bottom: 24px;
    }

    input, select, textarea {
      width: 100%;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      padding: 8px 12px;
      font-family: inherit;
      font-size: 14px;
      transition: border 0.15s;
      background: #fdfdfd;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-soft);
    }

    label {
      font-size: 13px;
      font-weight: 500;
      color: #374151;
      margin-bottom: 6px;
      display: block;
    }

    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px; }
    .grid-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px; }

    .btn {
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 500;
      font-size: 14px;
      cursor: pointer;
      border: 1px solid transparent;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }
    .btn.primary {
      background: var(--accent);
      color: #fff;
    }
    .btn.primary:hover { background: var(--accent-strong); }
    .btn.ghost { background: transparent; border-color: var(--line); color: var(--ink); }
    .btn.ghost:hover { background: #f3f4f6; }

    h2.section-title { margin: 0 0 4px; font-size: 18px; font-weight: 600; }
    p.subtle { color: var(--muted); font-size: 13px; margin: 0 0 20px; }

    .tab-panel { display: none; animation: fadeIn 0.15s ease-out; }
    .tab-panel.active { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

    .mode-switch {
      display: flex;
      flex-direction: column;
      background: #f9fafb;
      padding: 12px;
      border-radius: 8px;
      border: 1px solid #e5e7eb;
      margin-bottom: 20px;
    }
    .mode-label { font-size: 12px; font-weight: 600; text-transform: uppercase; color: #6b7280; margin-bottom: 8px; }
    .mode-buttons { display: flex; gap: 4px; }
    .mode-btn {
      padding: 6px 12px;
      font-size: 13px;
      border: 1px solid transparent;
      background: none;
      color: #4b5563;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 500;
    }
    .mode-btn:hover { background: #e5e7eb; }
    .mode-btn.active { background: #fff; color: var(--accent); border-color: #d1d5db; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
    .hint { font-size: 12px; color: #6b7280; margin-top: 8px; }
'''

# We will regex replace the CSS root to .shell { (not including shell since we rewrite it)
css_matcher = re.compile(r':root\s*\{.*?\}(?=\s*</style>)', re.DOTALL)
text = css_matcher.sub(new_css_root, text)

# 2. Update the HTML Body Structure
old_body_matcher = re.compile(r'<body>\s*<div class=\\"shell\\">\s*<header class=\\"card hero\\">.*?(?=<section class=\\"tab-panel active\\" id=\\"tab_overview\\">)', re.DOTALL)

new_body_top = '''<body>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="brand">
        <p class="eyebrow" id="hero_eyebrow">GenAI Operations</p>
        <h1 id="hero_title">Chief Control Plane</h1>
      </div>
      <nav class="nav-menu">
        <button class="tab-btn active" data-tab="overview" id="tab_btn_overview" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> Generate
        </button>
        <button class="tab-btn" data-tab="ops" id="tab_btn_ops" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg> Operations
        </button>
        <button class="tab-btn" data-tab="detail" id="tab_btn_detail" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> Run Detail
        </button>
        <button class="tab-btn" data-tab="modules" id="tab_btn_modules" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg> Modules
        </button>
      </nav>
      <div class="sidebar-footer">
        <div>
          <label for="lang_select" style="color:#aaa;font-size:11px;margin-bottom:4px" id="label_language">Language</label>
          <select id="lang_select">
            <option value="zh-TW">�c�餤��</option>
            <option value="en">English</option>
          </select>
        </div>
        <div>
          <label style="color:#aaa;font-size:11px;margin-bottom:4px;display:flex;align-items:center;gap:6px"><input id="auto_refresh" type="checkbox" checked style="width:auto"/> <span id="label_auto_refresh_text">Auto refresh</span></label>
        </div>
        <div>
          <select id="refresh_ms">
            <option value="1000">1s</option>
            <option value="2000" selected>2s</option>
            <option value="3000">3s</option>
            <option value="5000">5s</option>
          </select>
        </div>
        <button class="btn ghost mini" id="btn_refresh_now" type="button" style="color:#aaa;border-color:#555">Refresh now</button>
      </div>
    </aside>

    <main class="main-content">
      <header class="main-header">
        <div>
          <h2 style="margin:0;font-size:24px;font-weight:700">Dashboard</h2>
          <p class="subtle" id="hero_sub" style="margin-top:4px">Operate runs, inspect alerts, manage queue priority, and audit production history from one dashboard.</p>
        </div>
        <div class="hero-kpis">
          <div class="hero-kpi"><b id="kpi_label_system_state">System State</b><span id="kpi_system_state">idle</span></div>
          <div class="hero-kpi"><b id="kpi_label_queue_depth">Queue Depth</b><span id="kpi_queue_depth">0</span></div>
          <div class="hero-kpi"><b id="kpi_label_success_rate">Success Rate</b><span id="kpi_success_rate">0%</span></div>
          <div class="hero-kpi"><b id="kpi_label_avg_duration">Avg Duration</b><span id="kpi_avg_duration">-</span></div>
          <div class="hero-kpi"><b id="kpi_label_gpu_cost">Est. GPU Cost</b><span id="kpi_gpu_cost">.00</span></div>
        </div>
      </header>
'''
# Using sub with just replacing the top portion. We replace everything from body start to overview start.
text = old_body_matcher.sub(new_body_top.replace('\\', '\\\\'), text)

# Close the new div at the end of body
text = text.replace('</body>', '  </div>\n</body>')

with open('pipeline/templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(text)
