with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('Language</label>')
snippet = text[idx:idx+150]
print(repr(snippet))

try:
    print('Trying to reverse Big5 -> cp950:')
    # Assume PS interpreted UTF-8 bytes as CP950
    # Snippet is the unicode string
    # We want the original bytes
    orig_bytes = snippet.encode('cp950')
    print('bytes:', orig_bytes)
    # Now decode as utf-8
    print('Recovered:', orig_bytes.decode('utf-8'))
except Exception as e:
    print('Error:', e)
