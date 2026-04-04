import sys
with open('dashboard_html_temp.html', 'r', encoding='utf-8') as f: html = f.read()

# 1. Update NAV structure
nav_start = html.find('<nav class=\\"nav-menu\\">')
if nav_start == -1: nav_start = html.find('<nav class="nav-menu">')
nav_end = html.find('</nav>', nav_start) + 6
new_nav = '''<nav class=\\"nav-menu\\">
        <button class=\\"tab-btn active\\" data-tab=\\"overview\\" id=\\"tab_btn_overview\\" type=\\"button\\">
          <svg width=\\"16\\" height=\\"16\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\"><path d=\\"M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6\\"/></svg> 生成與設定
        </button>
        <button class=\\"tab-btn\\" data-tab=\\"workbench\\" id=\\"tab_btn_workbench\\" type=\\"button\\">
          <svg width=\\"16\\" height=\\"16\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\"><path d=\\"M12 20h9\\"/><path d=\\"M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z\\"/></svg> 專案資產調整
        </button>
        <button class=\\"tab-btn\\" data-tab=\\"playground\\" id=\\"tab_btn_playground\\" type=\\"button\\">
          <svg width=\\"16\\" height=\\"16\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\"><circle cx=\\"12\\" cy=\\"12\\" r=\\"10\\"/><path d=\\"M12 16v-4\\"/><path d=\\"M12 8h.01\\"/></svg> 一般 AI 工具
        </button>
        <button class=\\"tab-btn\\" data-tab=\\"ops\\" id=\\"tab_btn_ops\\" type=\\"button\\">
          <svg width=\\"16\\" height=\\"16\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\"><rect x=\\"3\\" y=\\"3\\" width=\\"18\\" height=\\"18\\" rx=\\"2\\" ry=\\"2\\"/><line x1=\\"3\\" y1=\\"9\\" x2=\\"21\\" y2=\\"9\\"/><line x1=\\"9\\" y1=\\"21\\" x2=\\"9\\" y2=\\"9\\"/></svg> Operations
        </button>
        <button class=\\"tab-btn\\" data-tab=\\"detail\\" id=\\"tab_btn_detail\\" type=\\"button\\">
          <svg width=\\"16\\" height=\\"16\\" viewBox=\\"0 0 24 24\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\"><path d=\\"M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z\\"/><polyline points=\\"14 2 14 8 20 8\\"/><line x1=\\"16\\" y1=\\"13\\" x2=\\"8\\" y2=\\"13\\"/><line x1=\\"16\\" y1=\\"17\\" x2=\\"8\\" y2=\\"17\\"/><polyline points=\\"10 9 9 9 8 9\\"/></svg> Run Details
        </button>
      </nav>'''
if nav_start != -1: html = html[:nav_start] + new_nav + html[nav_end:]

# 2. Update Generate Tab (Theme and subcategory)
old_theme_div = '''<div class=\\"grid-2 advanced-field\\">
              <div>
                <label for=\\"theme\\">Theme Hint (optional)</label>
                <input id=\\"theme\\" type=\\"text\\" placeholder=\\"ex: friendship, courage, mystery\\" />
              </div>
              <div>
                <label for=\\"subcategory\\">Subcategory Hint (optional)</label>  
                <input id=\\"subcategory\\" type=\\"text\\" placeholder=\\"ex: forest, tradition, science\\" />
              </div>
            </div>

            <div class=\\"grid-2 advanced-field\\">
              <div>
                <label for=\\"story_input_mode\\">Story Input Mode</label>        
                <select id=\\"story_input_mode\\">
                  <option value=\\"preset\\" selected>preset (use KG defaults)</option>
                  <option value=\\"custom\\">custom (convert user input)</option> 
                </select>
              </div>'''

new_theme_div = '''<div class=\\"grid-2 advanced-field\\">
              <div>
                <label for=\\"story_input_mode\\">輸入模式 (Story Input Mode)</label>        
                <select id=\\"story_input_mode\\" onchange=\\"toggleStoryInputMode()\\">
                  <option value=\\"preset\\" selected>預設 (Preset - KG default)</option>
                  <option value=\\"custom\\">自訂 (Custom - Manual text)</option> 
                </select>
              </div>
              <div id=\\"wrapper_custom_prompt\\" style=\\"display:none;\\">
                <label for=\\"custom_prompt\\">自訂故事提示 (Custom Prompt)</label>
                <textarea id=\\"custom_prompt\\" rows=\\"2\\" placeholder=\\"請輸入你想生成的故事內容...\\"></textarea>
              </div>
            </div>

            <div class=\\"grid-2 advanced-field\\" id=\\"wrapper_preset_meta\\">
              <div>
                <label for=\\"theme\\">主題 (Theme)</label>
                <select id=\\"theme\\">
                  <option value=\\"\\">auto</option>
                  <option value=\\"friendship\\">friendship</option>
                  <option value=\\"courage\\">courage</option>
                  <option value=\\"mystery\\">mystery</option>
                  <option value=\\"family\\">family</option>
                  <option value=\\"animals\\">animals</option>
                </select>
              </div>
              <div>
                <label for=\\"subcategory\\">子類別 (Subcategory)</label>  
                <select id=\\"subcategory\\">
                  <option value=\\"\\">auto</option>
                  <option value=\\"forest\\">forest</option>
                  <option value=\\"tradition\\">tradition</option>
                  <option value=\\"science\\">science</option>
                  <option value=\\"magic\\">magic</option>
                  <option value=\\"holiday\\">holiday</option>
                </select>
              </div>
            </div>
            
            <div class=\\"grid-2 advanced-field\\">
              '''
html = html.replace(old_theme_div, new_theme_div)

# 3. Workbench & Playground injection
modules_start = html.find('<section class=\\"tab-panel\\" id=\\"tab_modules\\">')
if modules_start != -1:
    script_mod_start = html.find('<script>', modules_start)
    old_modules_block = html[modules_start:script_mod_start]

    new_wb = '''<section class=\\"tab-panel\\" id=\\"tab_workbench\\">
      <div class=\\"main-header\\">
        <h2 class=\\"section-title\\">專案資產調整 (Story Asset Workbench)</h2>
        <p class=\\"subtle\\">在此進行特定故事書的翻譯覆寫、即時批次生成監控，以及圖片細調。</p>
      </div>

      <div class=\\"row-split\\">
        <section class=\\"card section\\">
          <h3>1. 批次生成即時監控 (Live Batch Viewer)</h3>
          <p class=\\"subtle\\" style=\\"font-size:12px;margin-top:-6px;\\">檢視當下剛剛生成的圖片，如不滿意可立即要求重繪(需搭配後端即時推播)</p>
          <div style=\\"border:1px dashed #d1d5db; border-radius:6px; padding:20px; text-align:center; color:#9ca3af; font-size:12px; min-height: 120px;\\">
            [ 此處接收 Batch WebSocket 流 ]
            <br/><button class=\\"btn ghost mini\\" style=\\"margin-top:10px;\\">載入預覽 Mock</button>
          </div>
        </section>

        <section class=\\"card section\\">
          <h3>2. 特定故事單張圖片調整 (Image Tweaking)</h3>
          <p class=\\"subtle\\" style=\\"font-size:12px;margin-top:-6px;\\">拉取先前故事產生的參數，調整後重新生成。</p>
          <div class=\\"grid-2\\">
            <div><label>Run ID</label><input type=\\"text\\" placeholder=\\"run_abc123\\" /></div>
            <div><label>第幾張 (Page #)</label><input type=\\"number\\" value=\\"1\\" /></div>
          </div>
          <button class=\\"btn ghost mini\\" style=\\"margin-bottom:12px;\\">載入圖片參數</button>
          
          <div style=\\"background:#f9fafb; padding:12px; border-radius:6px;\\">
            <div style=\\"text-align:center; margin-bottom:10px;\\">
               <div style=\\"width:100px; height:100px; background:#e5e7eb; border-radius:4px; display:inline-block; line-height:100px; font-size:11px; color:#9ca3af;\\">Image Preview</div>
            </div>
            <label>正面提示詞 (Positive Prompt)</label>
            <textarea rows=\\"2\\">A very cute puppy sleeping in the magical forest, 8k resolution, highly detailed</textarea>
            <label style=\\"margin-top:8px;\\">負面提示詞 (Negative Prompt)</label>
            <textarea rows=\\"1\\">blurry, text, dark, disfigured, sad</textarea>
            <div class=\\"grid-2\\" style=\\"margin-top:8px;\\">
              <div><label>Seed</label><input type=\\"text\\" value=\\"42123\\" /></div>
              <div><label>Steps</label><input type=\\"number\\" value=\\"30\\" /></div>
            </div>
            <button class=\\"btn primary mini\\" style=\\"margin-top:12px;width:100%\\">重啟生成 (Regenerate)</button>
          </div>
        </section>

        <section class=\\"card section\\">
          <h3>3. 專案翻譯覆蓋 (Story Translation Fixer)</h3>
          <p class=\\"subtle\\" style=\\"font-size:12px;margin-top:-6px;\\">針對特定書籍覆寫譯文或重跑 API。</p>
          <div class=\\"grid-2\\">
            <input type=\\"text\\" placeholder=\\"Run ID\\" />
            <select><option>Translate to zh-TW</option></select>
          </div>
          <button class=\\"btn ghost mini\\">翻譯覆寫 (Translate)</button>
        </section>
      </div>
    </section>

    <section class=\\"tab-panel\\" id=\\"tab_playground\\">
      <div class=\\"main-header\\">
        <h2 class=\\"section-title\\">一般 AI 工具 (AI Playground)</h2>
        <p class=\\"subtle\\">與故事產生無關的標準獨立呼叫介面，自由使用模型。</p>
      </div>

      <div class=\\"row-split\\">
        <div>
          <section class=\\"card section\\">
            <h3>通用文字模型 Chat (LLM)</h3>
            <label>System Prompt</label>
            <input type=\\"text\\" placeholder=\\"You are an expert...\\" style=\\"margin-bottom:8px;\\"/>
            <label>User Message</label>
            <textarea rows=\\"3\\" placeholder=\\"在此詢問一般問題或請 AI 寫文章...\\"></textarea>
            <button class=\\"btn primary mini\\" style=\\"margin-top:8px;\\">Send Message</button>
            <div style=\\"margin-top:8px; padding:12px; background:#f3f4f6; border-radius:4px; font-size:12px; min-height:80px; line-height:1.6;\\">在此會顯示標準的 AI 對話回覆。</div>
          </section>

          <section class=\\"card section\\">
            <h3>日常獨立翻譯 (Translate Tool)</h3>
            <div class=\\"grid-2\\" style=\\"margin-bottom:8px;\\">
               <select><option>AutoDetect</option><option>English</option><option>zh-TW</option></select>
               <select><option>zh-TW (繁體中文)</option><option>English</option><option>Japanese</option></select>
            </div>
            <textarea rows=\\"3\\" placeholder=\\"貼上想翻譯的一般文字...\\"></textarea>
            <button class=\\"btn primary mini\\" style=\\"margin-top:8px;\\">開始翻譯</button>
            <div style=\\"margin-top:8px; padding:12px; background:#f3f4f6; border-radius:4px; font-size:12px; min-height:60px;\\">譯文結果...</div>
          </section>
        </div>

        <div>
          <section class=\\"card section\\">
            <h3>獨立生圖畫布 (General txt2img)</h3>
            <label>正面提示詞 (Prompt)</label>
            <textarea rows=\\"2\\" placeholder=\\"A stunning futuristic city, cyber-punk, 4k background wallpaper...\\"></textarea>
            <label style=\\"margin-top:8px;\\">負面提示詞 (Negative)</label>
            <textarea rows=\\"1\\" placeholder=\\"bad quality, disfigured, text...\\"></textarea>
            <div class=\\"grid-3\\" style=\\"margin-top:8px;\\">
               <div><label>寬 (W)</label><input type=\\"number\\" value=\\"1024\\"/></div>
               <div><label>高 (H)</label><input type=\\"number\\" value=\\"1024\\"/></div>
               <div><label>Seed</label><input type=\\"text\\" placeholder=\\"auto\\"/></div>
            </div>
            <button class=\\"btn primary mini\\" style=\\"margin-top:8px;width:100%;\\">生成獨立圖片</button>
            <div style=\\"margin-top:12px; text-align:center;\\">
              <div style=\\"width:100%; height:200px; background:#e5e7eb; border-radius:6px; display:inline-block; line-height:200px; font-size:12px; color:#9ca3af;\\">Image Canvas</div>
            </div>
          </section>

          <section class=\\"card section\\">
            <h3>語音錄製與擴充合成 (Voice Studio)</h3>
            <label>麥克風錄音 (Web Audio Recorder)</label>
            <div style=\\"display:flex; gap:8px; margin-bottom:12px; align-items:center;\\">
              <button class=\\"btn ghost mini\\" id=\\"btn_record_audio\\" style=\\"color:var(--danger); border-color:var(--danger);\\">Start Recording</button>
              <span id=\\"record_status\\" style=\\"font-size:11px; color:var(--muted);\\">等待錄製... (麥克風)</span>
            </div>
            <hr style=\\"border:none; border-top:1px solid #e5e7eb; margin:12px 0;\\"/>
            <label>獨立語音合成 (Standard TTS)</label>
            <textarea rows=\\"2\\" placeholder=\\"輸入想轉成語音的獨立文字...\\"></textarea>
            <div class=\\"grid-2\\" style=\\"margin-top:8px;\\">
               <div><label>合成依據 (Voice Ref)</label>
               <select><option>剛才錄製好的音檔</option><option>上傳的 wav</option><option>系統預設 (XTTS)</option></select>
               </div>
               <div><label>語速 (Speed)</label><input type=\\"number\\" step=\\"0.1\\" value=\\"1.0\\" /></div>
            </div>
            <button class=\\"btn primary mini\\" style=\\"margin-top:8px;\\">Synthesize Audio</button>
          </section>
        </div>
      </div>
    </section>
\\n'''
    html = html.replace(old_modules_block, new_wb)

js_inj = """
    function toggleStoryInputMode() {
      const mode = document.getElementById('story_input_mode').value;
      const customWrapper = document.getElementById('wrapper_custom_prompt');
      const presetWrapper = document.getElementById('wrapper_preset_meta');
      if (mode === 'custom') {
        customWrapper.style.display = 'block';
        presetWrapper.style.display = 'none';
      } else {
        customWrapper.style.display = 'none';
        presetWrapper.style.display = 'grid'; // changed to grid
      }
    }
    
    // Auto attach recording logic on load
    setTimeout(() => {
        let btnRecord = document.getElementById('btn_record_audio');
        let mediaRecorder;
        let audioChunks = [];
        if (btnRecord) {
            btnRecord.addEventListener('click', async () => {
              const status = document.getElementById('record_status');
              if (btnRecord.innerText === 'Start Recording') {
                try {
                  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                  mediaRecorder = new MediaRecorder(stream);
                  mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
                  mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    status.innerHTML = <audio controls src="" style="height:30px;width:150px;"></audio>;
                  };
                  audioChunks = [];
                  mediaRecorder.start();
                  btnRecord.innerText = 'Stop Recording';
                  btnRecord.style.color = '#fff';
                  btnRecord.style.backgroundColor = 'var(--danger)';
                  status.innerText = '正在錄音...';
                } catch(e) { status.innerText = '無法存取麥克風 ' + e; }
              } else {
                mediaRecorder.stop();
                btnRecord.innerText = 'Start Recording';
                btnRecord.style.color = 'var(--danger)';
                btnRecord.style.backgroundColor = 'transparent';
              }
            });
        }
    }, 500);
"""
# Using exact string find
js_target = '// Elements'
html = html.replace(js_target, js_inj + '\\n    // Elements')

html = html.replace("const allowed = ['overview', 'ops', 'detail', 'modules'];",
                    "const allowed = ['overview', 'workbench', 'playground', 'ops', 'detail'];")

with open('dashboard_html_new.html', 'w', encoding='utf-8') as f:
    f.write(html)
