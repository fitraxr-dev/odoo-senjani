from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    senjani_order_status = fields.Selection([
        ('PENDING', 'Pending'),
        ('PROCESSED', 'Diproses'),
        ('IN_DELIVERY', 'Dikirim'),
        ('DONE', 'Selesai'),
    ], string='Senjani Order Status', compute='_compute_senjani_order_status', store=True)

    senjani_tracking_ref = fields.Char(
        string='Tracking Reference',
        compute='_compute_senjani_tracking_info',
        store=False,
    )

    senjani_tracking_url = fields.Char(
        string='Tracking URL',
        compute='_compute_senjani_tracking_info',
        store=False,
    )

    @api.depends('picking_ids', 'picking_ids.state', 'state')
    def _compute_senjani_order_status(self):
        for order in self:
            if order.state == 'cancel':
                order.senjani_order_status = False
                continue

            pickings = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
            done_pickings = pickings.filtered(lambda p: p.state == 'done')
            cancelled_pickings = pickings.filtered(lambda p: p.state == 'cancel')
            active_pickings = pickings.filtered(lambda p: p.state not in ('done', 'cancel'))

            if not pickings or all(p.state == 'cancel' for p in pickings):
                if order.state == 'done':
                    order.senjani_order_status = 'DONE'
                elif order.state == 'sale':
                    order.senjani_order_status = 'PENDING'
                else:
                    order.senjani_order_status = 'PENDING'
            elif all(p.state in ('done', 'cancel') for p in pickings):
                if order.state == 'done':
                    order.senjani_order_status = 'DONE'
                else:
                    # Semua pengiriman selesai, order belum di-done → Dikirim
                    order.senjani_order_status = 'IN_DELIVERY'
            elif done_pickings:
                order.senjani_order_status = 'IN_DELIVERY'
            elif active_pickings:
                order.senjani_order_status = 'PROCESSED'
            else:
                order.senjani_order_status = 'PENDING'

    def _compute_senjani_tracking_info(self):
        for order in self:
            pickings = order.picking_ids.filtered(
                lambda p: p.picking_type_id.code == 'outgoing' and p.carrier_tracking_ref
            ).sorted('date', reverse=True)
            if pickings:
                order.senjani_tracking_ref = pickings[0].carrier_tracking_ref
                order.senjani_tracking_url = pickings[0].carrier_tracking_url or False
            else:
                order.senjani_tracking_ref = False
                order.senjani_tracking_url = False
