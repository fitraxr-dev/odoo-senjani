from odoo import models, fields

class ResCity(models.Model):
    _inherit = 'res.city'

    rajaongkir_city_id = fields.Char(string='RajaOngkir City ID', help='ID kota dari RajaOngkir (misal 114 untuk Bandung)')