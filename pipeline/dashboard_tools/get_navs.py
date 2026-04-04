import re

with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

navs = re.findall(r'<button class="tab-btn".*?>(.*?)</button>', text, flags=re.DOTALL)
for n in navs:
    print(n.strip().replace('\n', ' '))
