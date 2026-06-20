from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('picking_ids', 'picking_ids.state', 'state', 'invoice_ids.state')
    def _compute_senjani_order_status(self):
        super()._compute_senjani_order_status()
        for order in self:
            if order.senjani_order_status in (False, 'PENDING'):
                posted_invoices = order.invoice_ids.filtered(lambda m: m.state == 'posted')
                if posted_invoices:
                    order.senjani_order_status = 'PROCESSED'

    def action_create_invoices_directly(self):
        self.ensure_one()
        invoices = self._create_invoices()
        if not invoices:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'No invoiceable lines found.',
                    'sticky': False,
                }
            }
        return self.action_view_invoice(invoices)
