from odoo import fields, models

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    down_payment = fields.Float(string='Down Payment', default=0.0)
    advance_payment_method = fields.Selection([
        ('delivered', 'Regular invoice'),
    ], string="Create Invoice", default='delivered', required=True)
