with open('dashboard_html_new.html', 'r', encoding='utf-8') as f: html = f.read()

js_inj = '''
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
                    status.innerHTML = <audio controls src="\\" style="height:30px;width:150px;"></audio>;
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
'''
html = html.replace("const allowed = [\\'overview\\', \\'workbench\\', \\'playground\\', \\'ops\\', \\'detail\\'];", js_inj + '\\n    ' + "const allowed = [\\'overview\\', \\'workbench\\', \\'playground\\', \\'ops\\', \\'detail\\'];")

with open('dashboard_html_new.html', 'w', encoding='utf-8') as f:
    f.write(html)
