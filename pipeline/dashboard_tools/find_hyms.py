import os
import time

history_path = os.path.expanduser('~/AppData/Roaming/Code/User/History')
import glob

results = []

for root, dirs, files in os.walk(history_path):
    for f in files:
        if not f.endswith('.py'): continue
        p = os.path.join(root, f)
        
        try:
            with open(p, 'r', encoding='utf-8') as file:
                content = file.read()
                if 'const I18N = {' in content and '_HTML =' in content and 'zh-TW' in content:
                    has_garble = '撠' in content or '鞈' in content or '?\x80' in content
                    if not has_garble:
                        results.append((os.path.getmtime(p), p))
        except:
            pass

results.sort(reverse=True)
for r in results[:5]:
    print(f"Time: {time.ctime(r[0])} | File: {r[1]}")
