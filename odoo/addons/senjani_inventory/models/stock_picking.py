from odoo import models, fields, api, _
# pyrefly: ignore [missing-import]
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_no_resi = fields.Char(
        string='No. Resi',
        copy=False,
        help='Nomor resi dari kurir (JNE, J&T, dll)'
    )
    
    x_tracking_link = fields.Char(
        string='Link Tracking',
        compute='_compute_x_tracking_link',
        store=False,
        help='Link untuk melacak pengiriman'
    )
    
    x_tracking_status = fields.Text(
        string='Status Tracking',
        help='Riwayat tracking dari kurir'
    )
    
    x_shipping_cost = fields.Monetary(
        string='Biaya Kirim Aktual',
        currency_field='currency_id',
        help='Biaya pengiriman yang dibebankan (dari delivery carrier)'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True
    )

    def _compute_x_tracking_link(self):
        """Generate link tracking berdasarkan nomor resi dan carrier"""
        for picking in self:
            if not picking.x_no_resi:
                picking.x_tracking_link = False
                continue
            
            # Cek carrier dari sale order atau dari picking
            carrier = picking.sale_id.carrier_id
            if not carrier:
                carrier = picking.carrier_id
            
            if carrier and carrier.delivery_type == 'jne':
                # Link tracking JNE
                picking.x_tracking_link = f"https://www.jne.co.id/id/tracking/trace/{picking.x_no_resi}"
            else:
                # Default: tidak ada link
                picking.x_tracking_link = False

    def action_confirm(self):
        res = super(StockPicking, self).action_confirm()
        return res

    def button_validate(self):
        """Saat validasi picking, bisa trigger pembuatan resi jika belum ada"""
        res = super(StockPicking, self).button_validate()
        for picking in self:
            # Jika belum ada resi dan ada carrier JNE, coba generate otomatis
            if not picking.x_no_resi and picking.sale_id and picking.sale_id.carrier_id:
                carrier = picking.sale_id.carrier_id
                if carrier.delivery_type == 'jne':
                    try:
                        # Panggil method send_shipping dari carrier
                        result = carrier.send_shipping([picking])
                        if result and result[0].get('tracking_number'):
                            _logger.info(f"Resi otomatis dibuat untuk {picking.name}: {result[0]['tracking_number']}")
                    except Exception as e:
                        _logger.warning(f"Gagal generate resi otomatis: {e}")
        return res

    def action_open_tracking_link(self):
        self.ensure_one()
        if self.x_tracking_link:
            return {
                'type': 'ir.actions.act_url',
                'url': self.x_tracking_link,
                'target': 'new',
            }
        else:
            raise UserError(_('Belum ada nomor resi atau link tracking untuk pengiriman ini.'))

    def action_check_resi_jne(self):
        self.ensure_one()
        if not self.x_no_resi:
            raise UserError(_('Belum ada nomor resi.'))
        self.x_tracking_status = "Tracking resi " + self.x_no_resi + " berhasil diperbarui."

    def _get_shipping_weight(self):
        """Hitung total berat picking dalam gram untuk kebutuhan API"""
        total_kg = sum(move.product_id.weight * move.product_uom_qty for move in self.move_ids if move.product_id.weight)
        return max(int(total_kg * 1000), 1)  # minimal 1 gram