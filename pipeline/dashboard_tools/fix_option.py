import re
with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()
text = re.sub(r'<option value="zh-TW">.*?</option>', '<option value="zh-TW">繁體中文</option>', text)
with open('pipeline/templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(text)
