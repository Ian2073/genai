import re, sys
html = open('test_clean.html', encoding='utf-8').read()
m = re.search(r'<script>(.*?)<\/script>', html, flags=re.DOTALL | re.IGNORECASE)
if m:
    with open('test_clean.js', 'w', encoding='utf-8') as f:
        f.write(m.group(1))
