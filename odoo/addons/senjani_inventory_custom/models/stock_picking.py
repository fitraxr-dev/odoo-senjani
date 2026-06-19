from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_no_resi = fields.Char(
        string="No. Resi",
        help="Nomor resi pengiriman dari kurir. Wajib diisi sebelum melakukan Validate."
    )

    def button_validate(self):
        # Hanya cek untuk Transfer keluar (Delivery Order) yang memiliki carrier
        for picking in self:
            if (
                picking.picking_type_code == 'outgoing'
                and picking.carrier_id
                and not picking.x_no_resi
            ):
                raise UserError(
                    _(
                        "Nomor Resi belum diisi!\n\n"
                        "Harap isi No. Resi terlebih dahulu sebelum melakukan Validate "
                        "pada pengiriman '%s'."
                    ) % picking.name
                )

        result = super().button_validate()

        # mengubah senjani_order_status ke IN_DELIVERY (Dikirim)
        for picking in self:
            if picking.picking_type_code == 'outgoing' and picking.state == 'done':
                if picking.x_no_resi and not picking.carrier_tracking_ref:
                    picking.carrier_tracking_ref = picking.x_no_resi

                for order in picking.sale_id:
                    if order.senjani_order_status == 'PROCESSED':
                        order.senjani_order_status = 'IN_DELIVERY'

        return result

    def action_check_resi_jne(self):
        self.ensure_one()
        if not self.x_no_resi:
            raise UserError(_('Belum ada nomor resi.'))
        self.x_tracking_status = "Tracking resi " + self.x_no_resi + " berhasil diperbarui."
