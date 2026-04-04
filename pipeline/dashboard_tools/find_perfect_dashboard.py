import os
import time

history_path = os.path.expanduser('~/AppData/Roaming/Code/User/History')

found = []
for root, dirs, files in os.walk(history_path):
    for f in files:
        p = os.path.join(root, f)
        # We want the dashboard.py that contained the string _HTML = '''<!doctype... OR _HTML = "...
        # and has "總覽" and "AI 工具" and "錄音"
        
        # Only check python files
        if not p.endswith('.py') and not p.endswith('dashboard.py.txt') and 'hyms.py' not in p and 'dashboard.py' not in p:
            continue
            
        try:
            with open(p, 'r', encoding='utf-8') as file:
                content = file.read()
                if 'class DashboardRuntime:' in content and '_HTML =' in content and 'data-tab="workbench"' in content:
                    found.append((os.path.getmtime(p), p))
        except:
            pass

found.sort(reverse=True)
for r in found[:5]:
    print(f"Time: {time.ctime(r[0])} | File: {r[1]}")
