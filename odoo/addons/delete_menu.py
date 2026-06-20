#!/usr/bin/env python3
menus = env['website.menu'].search([('url', '=', '/contactus')])
for m in menus:
    print(f"Deleting Menu: {m.name} (id={m.id})")
    m.unlink()
env.cr.commit()
print("Done deleting contact us menus.")
