with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'[\u4e00-\u9fff]+', text)
print(f"Total Chinese characters found: {len(matches)}")
print(', '.join(matches[:20]))
