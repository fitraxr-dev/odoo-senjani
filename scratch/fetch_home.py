import urllib.request

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request("http://127.0.0.1:8069/", headers=headers)
    response = urllib.request.urlopen(req)
    print("Status:", response.status)
    print("URL:", response.url)
    html = response.read().decode('utf-8')
    print("HTML Length:", len(html))
    print("HTML Title:", re.search(r'<title>(.*?)</title>', html))
except Exception as e:
    import re
    print("Error:", e)
