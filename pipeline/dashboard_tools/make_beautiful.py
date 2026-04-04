from bs4 import BeautifulSoup
import json
import re

print("Loading pristine HTML...")
with open('pipeline/templates/dashboard_restore.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

print("Modifying UI...")
# 1. Add Hardware Monitor
auto_refresh = soup.find(id='auto_refresh').parent
monitor_html = BeautifulSoup('''
<label class="inline-check"><span id="sys-status" style="font-weight: 800; color: var(--accent);">RAM: -- | GPU: --</span></label>
''', 'html.parser')
auto_refresh.insert_after(monitor_html)

# 2. Add Gallery Tab Button
tabs = soup.find('div', class_='tabs')
gallery_btn = BeautifulSoup('''
<button class="tab-btn" data-tab="gallery" id="tab_btn_gallery" type="button"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg> <span id="label_tab_gallery">Gallery</span></button>
''', 'html.parser')
# We also rename the other tabs slightly in HTML (they get overwritten by JS if I18N applies, but default to English)
tabs.append(gallery_btn)

# 3. Add Gallery Panel
header = soup.find('header')
gallery_panel = BeautifulSoup('''
<section class="tab-panel" id="tab_gallery">
  <div class="row-split">
    <section class="card section" style="width: 100%;">
      <h2 class="section-title">Gallery & History</h2>
      <p class="subtle">View recently generated images from output/ folders.</p>
      <div id="gallery_container" style="display:flex; flex-wrap:wrap; gap:14px; margin-top: 10px;">
        <span class="subtle">Loading gallery...</span>
      </div>
    </section>
  </div>
</section>
''', 'html.parser')
header.insert_after(gallery_panel)

# 4. Add Prompt Template UI to 'tab_overview' Story Prompt area
prompt_area = soup.find(id='story_prompt').parent
template_html = BeautifulSoup('''
<div style="margin-bottom: 8px; display: flex; gap: 8px;">
  <select id="template_select" style="flex: 1;">
    <option value="">-- Load a template --</option>
  </select>
  <button type="button" class="tab-btn" onclick="saveTemplate()" style="border-radius: 8px; padding: 4px 10px; margin: 0;">Save Template</button>
</div>
''', 'html.parser')
prompt_area.insert_before(template_html)

# 5. Inject New JS Logic & I18N adjustments
with open('pipeline/templates/dashboard_restore.html', 'r', encoding='utf-8') as f:
    text = str(soup)

# Update I18N translations safely
i18n_patch = '''
        'label.tab_gallery': '歷史作品庫 (Gallery)',
        'nav.overview': '總覽 (Generate)',
        'nav.modules': '專案資產調整 (Workbench & Tools)',
'''
text = text.replace("'nav.ops': 'Operations',", "'nav.ops': 'Operations',\n" + i18n_patch)
text = text.replace("'nav.ops': '維運 (Operations)',", "'nav.ops': '維運 (Operations)',\n" + i18n_patch)
text = text.replace("'nav.overview': 'Generation',", "'nav.overview': '總覽 (Generate)',")
text = text.replace("'nav.modules': 'Modules',", "'nav.modules': '單點工具 (Modules)',")

# Inject JS for API polling and Gallery
js_logic = '''
      // ----- NEW FEATURES -----
      function fetchGallery() {
        if(ui.activeTab !== 'gallery') return;
        fetch('/api/gallery').then(r=>r.json()).then(data => {
             const cont = document.getElementById('gallery_container');
             cont.innerHTML = '';
             data.images.forEach(img => {
                const el = document.createElement('div');
                el.style = 'border: 1px solid var(--line); padding: 5px; border-radius: 8px; background: #fff; text-align: center;';
                el.innerHTML = <img src="/" style="width: 180px; height: auto; border-radius: 4px;" /><br/>
                                <span class="subtle" style="font-size:10px;"></span>;
                cont.appendChild(el);
             });
             if(data.images.length===0) cont.innerHTML = '<span class="subtle">No images found.</span>';
        }).catch(e => console.error(e));
      }
      setInterval(fetchGallery, 3000);

      function pollSystemStatus() {
         fetch('/api/system')
         .then(r => r.json())
         .then(data => {
            const st = document.getElementById('sys-status');
            if(st) {
               st.innerHTML = RAM: % |  + 
                 data.gpus.map((g, i) => GPU: %).join(' | ');
               // apply color dynamically
               if (data.memory_percent > 85) st.style.color = 'var(--danger)';
               else st.style.color = 'var(--accent)';
            }
         }).catch(e => {});
      }
      setInterval(pollSystemStatus, 2500);

      window.saveTemplate = function() {
         const p = document.getElementById('story_prompt').value;
         if(!p) return alert('Prompt is empty');
         const name = prompt("請輸入這個 Prompt 的模板名稱 (Template name):", "兒童冒險故事");
         if(!name) return;
         fetch('/api/templates/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, prompt: p})
         }).then(() => fetchTemplates());
      };
      
      function fetchTemplates() {
         fetch('/api/templates').then(r=>r.json()).then(data=>{
            const select = document.getElementById('template_select');
            if(!select) return;
            select.innerHTML = '<option value="">-- 套用 Prompt 模板 (Load template) --</option>';
            data.forEach(t => {
               const opt = document.createElement('option');
               opt.value = t.prompt;
               opt.textContent = t.name;
               select.appendChild(opt);
            });
         }).catch(e=>console.log(e));
      }
      
      document.addEventListener('DOMContentLoaded', () => {
          fetchTemplates();
          pollSystemStatus();
          
          document.getElementById('template_select').addEventListener('change', (e) => {
              if (e.target.value) {
                  document.getElementById('story_prompt').value = e.target.value;
              }
          });
      });
      // -------------------------
'''
text = text.replace('setInterval(ui.pollStatus, 2000);', 'setInterval(ui.pollStatus, 2000);\n' + js_logic)

# ADD gallery to panels array
text = text.replace("      const panels = [", "      const panels = [\n        {name: 'gallery', id: 'tab_gallery'},")
text = text.replace("    function init() {", "    function init() {\n      const btn = document.getElementById('tab_btn_gallery');\n      if(btn) btn.addEventListener('click', () => { switchTab('gallery'); fetchGallery(); });\n")

with open('pipeline/templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Dashboard rebuilt beautifully, natively in UTF-8, applying all requested features.")
