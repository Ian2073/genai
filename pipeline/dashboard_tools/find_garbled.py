import re

with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Find any non-ascii characters strings
matches = set(re.findall(r'[^\x00-\x7F\r\n\t\s]+', text))
print("\n".join(matches))
