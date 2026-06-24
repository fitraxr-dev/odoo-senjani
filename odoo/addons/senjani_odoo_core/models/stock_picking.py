from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def write(self, vals):
        res = super().write(vals)
        # Jika nomor resi berubah, trigger recompute status pada sale order terkait
        if 'carrier_tracking_ref' in vals:
            sale_orders = self.mapped('sale_id').filtered(lambda o: o.id)
            if sale_orders:
                sale_orders._compute_senjani_order_status()
        return res
