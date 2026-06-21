from odoo import api, SUPERUSER_ID
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf'])
db = odoo.sql_db.db_connect('senjani_dev_db')
cr = db.cursor()
env = api.Environment(cr, SUPERUSER_ID, {})
payments = env['account.payment'].search([])
for p in payments:
    print('payment:', p.name, p.state, p.ref)
    for line in p.move_id.line_ids:
        if hasattr(line, 'reconciled_invoice_ids') and line.reconciled_invoice_ids:
            print('   reconciled to:', line.reconciled_invoice_ids.mapped('name'))
