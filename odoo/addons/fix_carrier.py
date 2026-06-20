from odoo.addons.senjani_sales_custom.models import sale_advance_payment_inv
carriers = env['delivery.carrier'].sudo().search([])
for c in carriers:
    print(f"Carrier: {c.name} | type={c.delivery_type} | fixed_price={c.fixed_price} | published={c.website_published} | active={c.active} | product_id={c.product_id.name}")
    # Ensure the fixed carrier is published and has proper product
    if c.delivery_type == 'fixed' and not c.website_published:
        c.website_published = True
        print(f"  -> Published '{c.name}' to website")

env.cr.commit()
print("\nDone!")
