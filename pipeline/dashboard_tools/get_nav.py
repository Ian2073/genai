import re
with open('pipeline/dashboard.py', 'r', encoding='utf-8') as f: text = f.read()

# get nav
m = re.search(r'<nav class="nav-menu">.*?</nav>', text, flags=re.DOTALL)
if m: print(m.group(0)[:500])
