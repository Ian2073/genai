import re
with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()
html = html.replace('data.memory_percent > 85', 'data.ram.percent > 85')
with open('pipeline/templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
