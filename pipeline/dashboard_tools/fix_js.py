import re

with open('make_beautiful.py', 'r', encoding='utf-8') as f:
    mb = f.read()

# Extract js_logic loosely
match = re.search(r"js_logic = '''(.*?)'''\ntext = text\.replace", mb, re.DOTALL)
if match:
    js = match.group(1)
    
    with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f2:
        html = f2.read()
        
    if "function fetchGallery()" not in html:
        html = html.replace("    function init() {", js + "\n    function init() {")
        with open('pipeline/templates/dashboard.html', 'w', encoding='utf-8') as f3:
            f3.write(html)
        print("JS Injected successfully!")
    else:
        print("Already injected.")
else:
    print("Could not find js_logic")
