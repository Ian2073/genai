with open('pipeline/templates/dashboard.html', 'rb') as f:
    text = f.read()

try:
    text.decode('utf-8')
    print("Is valid UTF-8!")
    
    with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()
        if "總控制台" in html:
            print("Contains expected Chinese Characters intact.")
except Exception as e:
    print(e)
