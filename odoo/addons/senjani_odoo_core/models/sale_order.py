from odoo import api, fields, models
from odoo.exceptions import AccessError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    senjani_order_status = fields.Selection([
        ('PENDING', 'Pending'),
        ('PROCESSED', 'Diproses'),
        ('IN_DELIVERY', 'Dikirim'),
        ('DONE', 'Selesai'),
    ], string='Senjani Order Status', compute='_compute_senjani_order_status',
       store=True, readonly=False)

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

            # Jika sudah DONE (ditandai pelanggan), jangan timpa nilainya
            if order.senjani_order_status == 'DONE' and order.state != 'cancel':
                continue

            pickings = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
            done_pickings = pickings.filtered(lambda p: p.state == 'done')
            active_pickings = pickings.filtered(lambda p: p.state not in ('done', 'cancel'))
            # Picking yang sudah done DAN sudah ada resi
            shipped_pickings = done_pickings.filtered(lambda p: p.carrier_tracking_ref)

            if not pickings or all(p.state == 'cancel' for p in pickings):
                # Belum ada pengiriman sama sekali
                order.senjani_order_status = 'PENDING'
            elif shipped_pickings:
                # Ada picking yang sudah divalidasi DAN sudah ada nomor resi → Dikirim
                order.senjani_order_status = 'IN_DELIVERY'
            elif done_pickings or active_pickings:
                # Picking ada (sedang diproses atau sudah done tapi belum ada resi) → Diproses
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

    def action_mark_order_received(self):
        """Dipanggil dari portal oleh pelanggan untuk menandai pesanan sudah diterima.
        Langsung set senjani_order_status = DONE tanpa bergantung pada state Odoo."""
        self.ensure_one()
        if self.partner_id != self.env.user.partner_id and not self.env.user.has_group('sales_team.group_sale_salesman'):
            raise AccessError('Anda tidak berhak mengubah pesanan ini.')
        if self.senjani_order_status == 'IN_DELIVERY':
            self.sudo().write({'senjani_order_status': 'DONE'})
        return True
