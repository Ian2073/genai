import re, sys

with open('pipeline/dashboard.py', 'r', encoding='utf-8') as f: text = f.read()

# 1. Update the CSS
new_css = '''    :root {
      --bg: #f9fafb;
      --bg-2: #f3f4f6;
      --card: #ffffff;
      --sidebar-bg: #111827;
      --sidebar-text: #d1d5db;
      --sidebar-hover: #1f2937;
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
      --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      height: 100vh;
      overflow: hidden;
    }

    /* === LAYOUT === */
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
      flex-shrink: 0;
      border-right: 1px solid #374151;
      z-index: 10;
    }

    .brand {
      padding: 24px 20px;
    }
    .brand h1 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: #fff;
      letter-spacing: 0.5px;
    }
    .brand p {
      margin: 0 0 2px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #9ca3af;
    }

    .nav-menu {
      padding: 12px;
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
      padding: 8px 12px;
      font-size: 14px;
      font-weight: 500;
      color: var(--sidebar-text);
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
      text-align: left;
    }
    .tab-btn svg { margin-right: 10px; width: 18px; height: 18px; stroke-width: 2; }
    .tab-btn:hover {
      background: var(--sidebar-hover);
      color: var(--sidebar-active);
    }
    .tab-btn.active {
      background: rgba(59, 130, 246, 0.15);
      color: #60a5fa;
    }

    .sidebar-footer {
      padding: 20px;
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      background: #0f141f;
    }
    .sidebar-footer select, .sidebar-footer input {
      background: #1f2937;
      border: 1px solid #374151;
      color: #f3f4f6;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 12px;
      width: 100%;
    }

    /* === MAIN CONTENT === */
    .main-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      padding: 32px 48px;
    }

    .main-header {
      margin-bottom: 32px;
    }
    
    .main-header h2 { margin: 0 0 6px; font-size: 24px; font-weight: 700; color: #111827; }
    .main-header p { margin: 0; color: var(--muted); font-size: 14px; }

    .hero-kpis {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }
    .hero-kpi {
      background: var(--card);
      padding: 16px;
      border-radius: 10px;
      border: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .hero-kpi b {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .hero-kpi span {
      font-size: 24px;
      font-weight: 700;
      color: var(--ink);
    }

    /* === CARDS & FORMS === */
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
      transition: all 0.15s;
      background: #ffffff;
      color: #111827;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
    }

    label {
      font-size: 13px;
      font-weight: 600;
      color: #374151;
      margin-bottom: 6px;
      display: block;
    }

    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px; }
    .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px; }

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
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .btn.primary:hover { background: var(--accent-strong); }
    .btn.ghost { background: #fff; border-color: #d1d5db; color: #374151; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
    .btn.ghost:hover { background: #f9fafb; border-color: #9ca3af; }
    .btn.mini { padding: 4px 10px; font-size: 12px; }

    h2.section-title { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #111827; }
    p.subtle { color: var(--muted); font-size: 13px; margin: 0 0 24px; line-height: 1.5; }

    .tab-panel { display: none; animation: fadeIn 0.15s ease-out; }
    .tab-panel.active { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

    /* Custom Mode Switch Matches Enterprise Look */
    .mode-switch {
      display: flex;
      flex-direction: column;
      background: #f9fafb;
      padding: 16px;
      border-radius: 8px;
      border: 1px solid #e5e7eb;
      margin-bottom: 24px;
    }
    .mode-label { font-size: 12px; font-weight: 700; text-transform: uppercase; color: #6b7280; margin-bottom: 10px; letter-spacing:0.5px; }
    .mode-buttons { display: flex; gap: 8px; background: #e5e7eb; padding: 4px; border-radius: 8px; width: max-content; }
    .mode-btn {
      padding: 6px 16px;
      font-size: 13px;
      border: none;
      background: transparent;
      color: #4b5563;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.15s;
    }
    .mode-btn:hover { color: #111827; }
    .mode-btn.active { background: #fff; color: #111827; box-shadow: 0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06); }
    .hint { font-size: 13px; color: #6b7280; margin-top: 10px; }

    /* Other Utilities */
    .inline-check { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; font-weight: 500; }
    .inline-check input { width: 16px; height: 16px; cursor: pointer; margin:0; }
    .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; text-transform: uppercase; background:#f3f4f6; color:#374151; }
    .pill.green { background: #dcfce7; color: #166534; }
    .pill.blue { background: #dbeafe; color: #1e40af; }
    .pill.red { background: #fee2e2; color: #991b1b; }
    .pill.orange { background: #fef3c7; color: #9a3412; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid var(--line); padding: 12px 8px; text-align: left; }
    th { font-weight: 600; color: #6b7280; text-transform: uppercase; font-size: 11px; }
    td { color: #111827; }
    tbody tr:hover { background: #f9fafb; }
'''

# First, extract existing CSS block
css_matcher = re.search(r'<style>(.*?)<\/style>', text, flags=re.DOTALL)
if css_matcher:
    old_css = css_matcher.group(1)
    
    # We replace from :root down to table styles, keeping module/queue styles
    # Find the end of basic body/layout styles or we can just replace everything and append the module specifics:
    # Actually, the original CSS has many specific things like .row-split, .image-gallery. We must keep those!
    # So we replace :root {...} up to .tab-panel.active {...}
    replace_marker = re.search(r':root\s*\{.*?\.tab-panel\.active\s*\{[^\}]+\}', old_css, flags=re.DOTALL)
    if replace_marker:
        updated_css = old_css[:replace_marker.start()] + new_css + old_css[replace_marker.end():]
        text = text.replace(old_css, updated_css)
        print("CSS replaced.")
    else:
        print("Could not find CSS replace marker")

# 2. Update the HTML Body Structure
old_body_matcher = re.search(r'(<body>)\s*(<div class=\\"shell\\">.*?)(<section class=\\"tab-panel active\\" id=\\"tab_overview\\">)', text, flags=re.DOTALL)

new_body_top = '''<body>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="brand">
        <p class="eyebrow" id="hero_eyebrow" style="margin:0 0 4px;font-size:11px;text-transform:uppercase;color:#9ca3af">GenAI Operations</p>
        <h1 id="hero_title" style="margin:0;font-size:16px;color:#fff">Chief Control Plane</h1>
      </div>
      <nav class="nav-menu">
        <button class="tab-btn active" data-tab="overview" id="tab_btn_overview" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> Generate
        </button>
        <button class="tab-btn" data-tab="ops" id="tab_btn_ops" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg> Operations
        </button>
        <button class="tab-btn" data-tab="detail" id="tab_btn_detail" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> Run Detail
        </button>
        <button class="tab-btn" data-tab="modules" id="tab_btn_modules" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg> Modules
        </button>
      </nav>
      <div class="sidebar-footer">
        <div>
          <label for="lang_select" id="label_language" style="color:#9ca3af;font-size:11px;margin-bottom:6px">Language</label>
          <select id="lang_select">
            <option value="zh-TW">¡c≈È§§§Â</option>
            <option value="en">English</option>
          </select>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <input id="auto_refresh" type="checkbox" checked style="width:auto;margin:0" /> 
          <label for="auto_refresh" id="label_auto_refresh_text" style="color:#d1d5db;font-size:12px;margin:0;font-weight:400;cursor:pointer">Auto refresh</label>
        </div>
        <div>
          <select id="refresh_ms">
            <option value="1000">1s</option>
            <option value="2000" selected>2s</option>
            <option value="3000">3s</option>
            <option value="5000">5s</option>
          </select>
        </div>
        <button class="btn ghost" id="btn_refresh_now" type="button" style="width:100%;color:#d1d5db;border-color:#374151;background:transparent">Refresh now</button>
      </div>
    </aside>

    <main class="main-content">
      <header class="main-header">
        <h2>Dashboard</h2>
        <p class="subtle" id="hero_sub">Operate runs, inspect alerts, manage queue priority, and audit production history from one dashboard.</p>
        <div class="hero-kpis">
          <div class="hero-kpi"><b id="kpi_label_system_state">System State</b><span id="kpi_system_state">idle</span></div>
          <div class="hero-kpi"><b id="kpi_label_queue_depth">Queue Depth</b><span id="kpi_queue_depth">0</span></div>
          <div class="hero-kpi"><b id="kpi_label_success_rate">Success Rate</b><span id="kpi_success_rate">0%</span></div>
          <div class="hero-kpi"><b id="kpi_label_avg_duration">Avg Duration</b><span id="kpi_avg_duration">-</span></div>
          <div class="hero-kpi"><b id="kpi_label_gpu_cost">Est. GPU Cost</b><span id="kpi_gpu_cost">.00</span></div>
        </div>
      </header>
'''

if old_body_matcher:
    text = text.replace(old_body_matcher.group(0), new_body_top + '<section class="tab-panel active" id="tab_overview">')
    print("Body replaced.")
else:
    print("Could not find body replace marker")

# Inject closing div for app-layout right before </body>
text = text.replace('</body>', '  </div>\n</body>')

with open('pipeline/dashboard.py', 'w', encoding='utf-8') as f:
    f.write(text)
