import os

addons_path = '/usr/lib/python3/dist-packages/odoo/addons'
xml_files = []
for root, dirs, files in os.walk(addons_path):
    for f in files:
        if f.endswith('.xml'):
            xml_files.append(os.path.join(root, f))

output = []
for file_path in xml_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'inherit_id="website_sale.cart_lines"' in content or "inherit_id='website_sale.cart_lines'" in content:
                # Find matching lines
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if 'inherit_id=' in line and 'website_sale.cart_lines' in line:
                        output.append(f"{file_path}:{i+1}: {line.strip()}")
    except Exception as e:
        pass

with open('/mnt/extra-addons/find_cart_lines_inherit_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("Cart lines inherit search completed")
