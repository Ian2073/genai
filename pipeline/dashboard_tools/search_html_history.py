import os
import time

history_path = os.path.expanduser('~/AppData/Roaming/Code/User/History')
import glob

now = time.time()
results = []

for root, dirs, files in os.walk(history_path):
    for f in files:
        p = os.path.join(root, f)
        
        # skip old files (more than 24 hours old)
        if now - os.path.getmtime(p) > 86400:
            continue
            
        try:
            with open(p, 'r', encoding='utf-8') as file:
                content = file.read()
                if 'data-tab="workbench"' in content and '<html' in content:
                    has_garble = '撠' in content or '鞈' in content or '?\x80' in content or '' in content
                    has_gallery = 'fetchGallery' in content
                    results.append((os.path.getmtime(p), has_garble, has_gallery, p))
        except:
            pass

results.sort(reverse=True)
for r in results[:20]:
    print(f"Time: {time.ctime(r[0])} | Garble: {r[1]} | Gallery: {r[2]} | File: {r[3]}")
