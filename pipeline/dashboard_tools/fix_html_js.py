import re

with open('pipeline/templates/dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the broken JS
bad_js1 = r'el\.innerHTML = <img src="/" style="width: 180px; height: auto; border-radius: 4px;" /><br/>\s*<span class="subtle" style="font-size:10px;"></span>;'
good_js1 = "el.innerHTML = '<img src=\"' + (img.cover ? ('/api/images/file?path=' + encodeURIComponent(img.cover)) : '') + '\" style=\"width: 180px; height: auto; border-radius: 4px;\" /><br/>' + '<span class=\"subtle\" style=\"font-size:10px;\">' + img.title + '</span>';"
html = re.sub(bad_js1, good_js1, html)

bad_js2 = r'st\.innerHTML = RAM: % \|  \+\s*data\.gpus\.map\(\(g, i\) => GPU: %\)\.join\(\' \| \'\);'
good_js2 = "st.innerHTML = 'RAM: ' + data.ram.percent + '% | ' + data.gpus.map((g, i) => 'GPU' + i + ': ' + g.gpu_util + '%').join(' | ');"
html = re.sub(bad_js2, good_js2, html)

bad_js3 = r'st\.innerHTML = RAM: % \|  \+\s*data\.gpus\.map\(\(g, i\) => GPU: %\)\.join\(\' \| \'\);'
html = html.replace("else st.style.color = 'var(--accent)';", "else st.style.color = 'var(--accent)';") # just a marker

# Write HTML back out
with open('pipeline/templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("HTML JS fixed!")
