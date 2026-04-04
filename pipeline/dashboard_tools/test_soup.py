from bs4 import BeautifulSoup

print("Loading pristine HTML...")
with open('pipeline/templates/dashboard_restore.html', 'r', encoding='utf-8') as f:
    text = f.read()

soup = BeautifulSoup(text, 'html.parser')
res = soup.find(id='auto_refresh')
print('Res:', res)

if res is None:
    # Maybe the string is broken?
    import re
    print("re search:", re.search(r'id=\"auto_refresh\"', text) is not None)
