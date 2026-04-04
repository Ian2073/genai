import os
import json
from pathlib import Path

history_dir = Path(os.environ['APPDATA']) / 'Code' / 'User' / 'History'
for entries_file in history_dir.rglob('entries.json'):
    try:
        with open(entries_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            url = data.get('resource', '')
            if 'pipeline%5Cdashboard.py' in url or 'pipeline/dashboard.py' in url or 'dashboard.py' in url or 'dashboard.html' in url:
                print('Found in:', entries_file)
                print(data)
    except:
        pass
