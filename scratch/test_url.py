import urllib.request
import re

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # First get a product URL from shop page
    req = urllib.request.Request("http://127.0.0.1:8069/shop?db=senjani", headers=headers)
    shop_html = urllib.request.urlopen(req).read().decode("utf-8")
    product_urls = re.findall(r'href="/shop/[^"?]+"', shop_html)
    print("Found product URLs:", product_urls[:10])
    
    # Let's find one that looks like a product URL (e.g. /shop/hijab-khimar-45 or /shop/product/...)
    product_url = None
    for url in product_urls:
        url_path = url.split('"')[1]
        if "/shop/product/" in url_path or (len(url_path.split("/")) == 3 and not url_path.endswith("/cart") and not url_path.endswith("/checkout")):
            product_url = url_path
            break
            
    if not product_url:
        # Fallback to a default one
        product_url = "/shop/hijab-khimar-45"
        
    print("Fetching product page:", product_url)
    req2 = urllib.request.Request(f"http://127.0.0.1:8069{product_url}?db=senjani", headers=headers)
    p_html = urllib.request.urlopen(req2).read().decode("utf-8")
    
    # Find the css_quantity block
    qty_matches = re.findall(r'<div[^>]*class="[^"]*css_quantity[^"]*"[^>]*>.*?</div>', p_html, re.DOTALL)
    print("Found qty matches:", len(qty_matches))
    for i, m in enumerate(qty_matches):
        print(f"Match {i+1}:")
        print(m)
        
    # Also print the larger context around css_quantity
    match_index = p_html.find('class="css_quantity')
    if match_index != -1:
        print("\n--- CONTEXT ---")
        print(p_html[max(0, match_index - 300): min(len(p_html), match_index + 1200)])
except Exception as e:
    print("Error:", e)
