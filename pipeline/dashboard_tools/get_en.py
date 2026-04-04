import re

with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Grab the English dictionary
m = re.search(r"'en': \{(.*?)\},", text, re.DOTALL)
en_dict = m.group(1)

# Now what are the keys? Let's print them.
keys = re.findall(r"'([\w.]+)':", en_dict)
print(", ".join(keys))
