from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super(AccountMove, self).action_post()
        sale_orders = self.line_ids.sale_line_ids.order_id
        if sale_orders:
            for order in sale_orders:
                if order.senjani_order_status in (False, 'PENDING'):
                    order.senjani_order_status = 'PROCESSED'
        return res
