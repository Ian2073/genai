import re

with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Grab anything that's not ASCII and print its context
matches = re.finditer(r'([^\x00-\x7F]+)', text)
found_garble = []
for m in matches:
    g = m.group(1)
    # Exclude normal Chinese we knowingly wrote:
    if any(c in g for c in ['總', '控', '制', '台', '單', '一', '儀', '表', '板', '管', '理', '執', '行', '檢', '查', '繁', '體', '中', '文', '歷', '史', '作', '品', '庫', '專', '案', '資', '產', '調', '整', '兒', '童', '冒', '險', '故', '事', '輸', '入', '這', '個', '模', '板', '名', '稱']):
        continue
    # Print the weird ones
    print(f"Unknown characters: {g}")
    found_garble.append(g)

if not found_garble:
    print("Clean!")
