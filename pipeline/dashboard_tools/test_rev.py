import chardet
# Let's read some garbled text and trace its origin
with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

garbled = text[text.find('Language</label>'):text.find('Language</label>')+100]
print(repr(garbled))
