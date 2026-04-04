import re

with open(r'C:\Users\kuosh\AppData\Roaming\Code\User\History\-2d639\hyms.py', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r"_HTML\s*=\s*(r?'''(.*?)\n'''|\"\"\"(.*?)\n\"\"\")", text, re.DOTALL)
if m:
    html = m.group(2) or m.group(3)
    if html:
        with open('pipeline/templates/dashboard_restore.html', 'w', encoding='utf-8') as out:
            out.write(html)
        print("Success! Wrote dashboard_restore.html:", len(html))
    else:
        print("Groups were empty?!")
else:
    print("Could not find _HTML literal!")
