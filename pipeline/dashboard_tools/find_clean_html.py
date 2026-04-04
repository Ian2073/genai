import os
import glob

history_path = os.path.expanduser('~/AppData/Roaming/Code/User/History/*/dashboard.html')
files = glob.glob(history_path)
files.sort(key=os.path.getmtime, reverse=True)

import time

count = 0
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
            # Find the one that has valid Chinese "歷史作品庫" and isn't garbled yet. Wait, no.
            # I want the one that is just the beautiful original dashboard.html, which has "const I18N = {" and " zh-TW: {"
            # AND it doesn't have 撠
            
            if 'const I18N = {' in content and 'zh-TW' in content and '撠' not in content and '\uee02' not in content:
                print(f"CLEAN FILE: {f} | {time.ctime(os.path.getmtime(f))} | size: {len(content)}")
                count += 1
                if count > 5: break
    except:
        pass
