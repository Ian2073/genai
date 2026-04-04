with open('pipeline/templates/dashboard_restore.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix python escaped strings if they exist
text = text.replace('\\"', '"')
text = text.replace("\\'", "'")
text = text.replace('\\\\', '\\')

with open('pipeline/templates/dashboard_restore.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Un-escaped!")
