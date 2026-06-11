from odoo import models, fields, api
import random
import logging
import requests

_logger = logging.getLogger(__name__)

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('jne', 'JNE Express (RajaOngkir)')],
        ondelete={'jne': 'set default'},
    )

    def _get_rajaongkir_api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param('rajaongkir.api_key', '')


    def jne_rate_shipment(self, order):
        api_key = self._get_rajaongkir_api_key()
        if not api_key:
            return {
                'success': False,
                'price': 0,
                'error_message': 'API Key RajaOngkir belum dikonfigurasi. Hubungi administrator.',
                'warning_message': False,
            }

        # Hitung total berat (kg)
        total_weight_gram = sum(
            line.product_id.weight * line.product_uom_qty
            for line in order.order_line
            if line.product_id.type in ('product', 'consu')
        )
        if total_weight_gram <= 0:
            total_weight_gram = 1000  # minimal 1 kg

        company = order.company_id or self.env.company
        origin_city_id = company.partner_id.city_id.rajaongkir_city_id if company.partner_id.city_id else False
        if not origin_city_id:
            origin_city_id = 501
            _logger.warning("Origin city ID tidak ditemukan, menggunakan default 501")

        dest_city_id = order.partner_shipping_id.city_id.rajaongkir_city_id if order.partner_shipping_id.city_id else False
        if not dest_city_id:
            # Bisa coba dari partner itu sendiri
            dest_city_id = order.partner_id.city_id.rajaongkir_city_id if order.partner_id.city_id else False
        if not dest_city_id:
            return {
                'success': False,
                'price': 0,
                'error_message': 'Alamat tujuan tidak memiliki kota yang valid. Silakan lengkapi data kota.',
                'warning_message': False,
            }

        url = "https://api.rajaongkir.com/starter/cost"
        headers = {"key": api_key, "content-type": "application/x-www-form-urlencoded"}
        payload = {
            "origin": origin_city_id,
            "destination": dest_city_id,
            "weight": int(total_weight_gram),  # dalam gram
            "courier": "jne"
        }

        try:
            response = requests.post(url, data=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                result = response.json()
                costs = result['rajaongkir']['results'][0]['costs']
                for service in costs:
                    if service['service'] == 'REG':
                        price = service['cost'][0]['value']
                        etd = service['cost'][0]['etd']
                        return {
                            'success': True,
                            'price': price,
                            'error_message': False,
                            'warning_message': f'Estimasi tiba: {etd} hari (JNE REG)',
                        }
                # Jika REG tidak tersedia, ambil yang termurah dari JNE
                if costs:
                    min_cost = min(costs, key=lambda x: x['cost'][0]['value'])
                    price = min_cost['cost'][0]['value']
                    return {
                        'success': True,
                        'price': price,
                        'error_message': False,
                        'warning_message': f'Menggunakan layanan {min_cost["service"]} ({min_cost["description"]})',
                    }
                else:
                    return {
                        'success': False,
                        'price': 0,
                        'error_message': 'JNE tidak tersedia untuk rute ini.',
                        'warning_message': False,
                    }
            else:
                error_msg = f"RajaOngkir error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                return {
                    'success': False,
                    'price': 0,
                    'error_message': error_msg,
                    'warning_message': False,
                }
        except Exception as e:
            _logger.exception("Gagal memanggil RajaOngkir")
            return {
                'success': False,
                'price': 0,
                'error_message': f"Gagal koneksi ke RajaOngkir: {str(e)}",
                'warning_message': False,
            }

    def jne_send_shipping(self, pickings):
        result = []
        for picking in pickings:
            random_num = random.randint(10_000_000_000, 99_999_999_999)
            resi_number = f"JNE-REG-{random_num}"
            picking.x_no_resi = resi_number
            result.append({
                'exact_price': 0,
                'tracking_number': resi_number,
            })
        return result

    def jne_get_tracking_link(self, picking):
        if picking.x_no_resi:
            return f"https://www.jne.co.id/id/tracking/trace/{picking.x_no_resi}"
        return False

    def jne_cancel_shipment(self, pickings):
        # Untuk sementara tidak melakukan apa-apa, hanya log
        for picking in pickings:
            _logger.warning("Pembatalan pengiriman JNE untuk %s (resi: %s) belum diimplementasikan.",
                            picking.name, picking.x_no_resi or '-')
        return None