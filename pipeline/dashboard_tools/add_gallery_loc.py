import re
with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

arr_insert = "        ['tab_btn_gallery', 'label.tab_gallery', 'Gallery'],\n"
if "'label.tab_gallery'" not in text:
    text = text.replace("        ['tab_btn_overview', 'tab.overview', 'Generate'],", arr_insert + "        ['tab_btn_overview', 'tab.overview', 'Generate'],")
    with open('pipeline/templates/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Gallery localization mapped.")
