import re
with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

btn_modules = '''        <button class="tab-btn" data-tab="modules" id="tab_btn_modules" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg> Modules
        </button>'''

btn_gallery = '''        <button class="tab-btn" data-tab="gallery" id="tab_btn_gallery" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg> <span id="label_tab_gallery">Gallery</span>
        </button>'''

if 'id="tab_btn_gallery"' not in text[:text.find('</nav>')]:
    text = text.replace(btn_modules, btn_gallery + '\n' + btn_modules)
    
with open('pipeline/templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Gallery button added to sidebar!")
