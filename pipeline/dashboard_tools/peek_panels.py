import re

with open('pipeline/templates/dashboard_restore.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
panels = re.findall(r'<div[^>]*id="(panel_[^"]+)"', text)
print("Panels:", panels)
