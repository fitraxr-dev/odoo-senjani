from odoo import api, SUPERUSER_ID
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf'])
db = odoo.sql_db.db_connect('senjani_dev_db')
cr = db.cursor()
env = api.Environment(cr, SUPERUSER_ID, {})

bills = env['account.move'].search([('move_type', '=', 'in_invoice'), ('payment_state', 'in', ('in_payment', 'paid'))])
for bill in bills:
    if not bill.payment_reference:
        payments = bill._get_reconciled_payments()
        if payments:
            bill.payment_reference = payments[0].name

env.cr.commit()
