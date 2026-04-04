with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()
print(text.find('歷史作品庫'))
print(repr(text[text.find('歷史'):text.find('歷史')+20]))
