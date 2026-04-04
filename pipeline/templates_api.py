import json
from pathlib import Path

TEMPLATES_FILE = Path("runs/prompt_templates.json")

def load_templates():
    if not TEMPLATES_FILE.exists():
        return []
    try:
        with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_template(name, prompt, negative_prompt):
    data = load_templates()
    data.append({"name": name, "prompt": prompt, "negative_prompt": negative_prompt})
    TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data
