import requests
from odoo import models, fields, api

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('rajaongkir', 'RajaOngkir API')], 
        ondelete={'rajaongkir': 'set default'}
    )
    rajaongkir_api_key = fields.Char(string="API Key RajaOngkir")

    # Fungsi Baru: Cek ID dinamis menggunakan API Search RajaOngkir
    def _get_ro_id_from_api(self, zip_code):
        if not zip_code:
            return False
            
        zip_clean = str(zip_code).strip()
        
        try:
            # Menembak endpoint pencarian langsung (bisa menggunakan kode pos)
            url = f"https://rajaongkir.komerce.id/api/v1/destination/search?search={zip_clean}"
            headers = {
                'Key': self.rajaongkir_api_key or '',
                'Accept': 'application/json'
            }
            
            # Tambahkan timeout 5 detik agar jika server RajaOngkir lambat, Odoo tidak ikut nge-hang
            response = requests.get(url, headers=headers, timeout=5)
            response_data = response.json()
            
            # Jika status sukses dan ada data yang cocok dengan kode pos tersebut
            if response_data.get('meta', {}).get('status') == 'success' and len(response_data.get('data', [])) > 0:
                # API akan mengembalikan list wilayah. Kita langsung ambil ID urutan pertama (index 0).
                return str(response_data['data'][0]['id'])
                
        except Exception as e:
            pass # Abaikan jika error, nanti ditangkap di fungsi utama
            
        return False

    def rajaongkir_rate_shipment(self, order):
        try:
            # 1. Ambil kode pos dari Toko dan Pembeli
            zip_toko = self.env.company.partner_id.zip
            zip_pembeli = order.partner_shipping_id.zip

            # 2. Minta Odoo untuk otomatis mencari ID-nya via API
            origin_id = self._get_ro_id_from_api(zip_toko)
            destination_id = self._get_ro_id_from_api(zip_pembeli)

            if not origin_id or not destination_id:
                return {
                    'success': False, 
                    'price': 0.0, 
                    'error_message': f"Gagal: Kode Pos Toko ({zip_toko}) atau Pembeli ({zip_pembeli}) tidak terdeteksi oleh sistem pencarian RajaOngkir.", 
                    'warning_message': False
                }

            # 3. Hitung Berat Barang (Odoo defaultnya KG, API butuhnya Gram)
            total_weight_kg = sum([(line.product_id.weight * line.product_uom_qty) for line in order.order_line])
            
            total_weight_gram = int((total_weight_kg or 1.0) * 1000)
            if total_weight_gram < 1000:
                total_weight_gram = 1000

            # 4. Request harga ke API RajaOngkir
            url = "https://rajaongkir.komerce.id/api/v1/calculate/district/domestic-cost"
            headers = {
                'Key': self.rajaongkir_api_key or '',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            payload = {
                'origin': origin_id,
                'destination': destination_id,
                'weight': total_weight_gram,
                'courier': 'jne',
                'price': 'lowest'
            }

            response = requests.post(url, headers=headers, data=payload, timeout=10)
            response_data = response.json()

            # 5. Tangkap Output Harga
            if response_data.get('meta', {}).get('status') == 'success':
                ongkir_value = response_data['data'][0]['cost'] 
                return {'success': True, 'price': ongkir_value, 'error_message': False, 'warning_message': False}
            else:
                raise Exception(response_data.get('meta', {}).get('message', 'Error API Perhitungan'))

        except Exception as e:
            return {'success': False, 'price': 0.0, 'error_message': f"Gagal menghitung ongkir: {str(e)}", 'warning_message': False}