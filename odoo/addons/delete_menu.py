#!/usr/bin/env python3
menus = env['website.menu'].search([('name', 'ilike', 'Contact')])
print(f"Menus to delete: {menus}")
if menus:
    menus.unlink()
    env.cr.commit()
    print("Done deleting contact us menus.")
else:
    print("No contact us menu found.")
