with open('C:/Users/kuosh/AppData/Roaming/Code/User/History/-2d639/hyms.py', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('_HTML = \"\"\"')
end = text.find('\"\"\"', start + 12)

html_content = text[start + 11:end]

with open('pipeline/templates/dashboard_restore.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("Saved cleanly extracted HTML to dashboard_restore.html")
