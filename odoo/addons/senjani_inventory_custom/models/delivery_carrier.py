import requests
from odoo import models, fields, api

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('rajaongkir', 'RajaOngkir API')], 
        ondelete={'rajaongkir': 'set default'}
    )
    rajaongkir_api_key = fields.Char(string="API Key RajaOngkir")

    # Fungsi Mapping: Ubah Kode Pos (Zip) menjadi ID Kecamatan RajaOngkir
    def _get_ro_district_id_by_zip(self, zip_code):
        # Jika pelanggan tidak mengisi kode pos, langsung default ke Garut
        if not zip_code:
            return '1805' # Ganti '1805' dengan ID asli Garut dari RajaOngkir nanti
            
        # Bersihkan spasi (berjaga-jaga jika admin salah ketik spasi di ujung)
        zip_clean = str(zip_code).strip()

        # KAMUS KODE POS -> ID RAJAONGKIR
        zip_to_ro_id = {
            '44181': '1805', # Alamat Toko (Garut) -> ID Dummy: 1805
            '55434': '5543', # ID Dummy: 5543
            '40559': '4055', # ID Dummy: 4055
            '40132': '1391', # Kode Pos 40132 (Coblong, Bandung) -> ID RO: 1391
            '40111': '1376', # Kode Pos 40111 (Sumur Bandung) -> ID RO: 1376
            '12110': '1362', # Kode Pos 12110 (Kebayoran Baru, Jaksel) -> ID RO: 1362
            '12810': '1369', # Kode Pos 12810 (Tebet, Jaksel) -> ID RO: 1369
        }

        # Cari di kamus. 
        # Jika ditemukan, kembalikan ID-nya.
        # Jika TIDAK DITEMUKAN, gunakan parameter kedua ('1805') sebagai default / fallback ke Garut.
        return zip_to_ro_id.get(zip_clean, '1805')

    def rajaongkir_rate_shipment(self, order):
        try:
            # 1. Ambil kode pos dari Toko dan Pembeli
            zip_toko = self.env.company.partner_id.zip
            zip_pembeli = order.partner_shipping_id.zip

            # Panggil fungsi mapping di atas
            # Karena sudah ada fallback di fungsinya, variabel ini tidak akan pernah kosong
            origin_id = self._get_ro_district_id_by_zip(zip_toko)
            destination_id = self._get_ro_district_id_by_zip(zip_pembeli)

            # 2. Hitung Berat Barang (Odoo defaultnya KG, API butuhnya Gram)
            total_weight_kg = sum([(line.product_id.weight * line.product_uom_qty) for line in order.order_line])
            
            total_weight_gram = int((total_weight_kg or 1.0) * 1000)
            if total_weight_gram < 1000:
                total_weight_gram = 1000

            # 3. Request ke API RajaOngkir
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

            response = requests.post(url, headers=headers, data=payload)
            response_data = response.json()

            # 4. Tangkap Output Harga
            if response_data.get('meta', {}).get('status') == 'success':
                ongkir_value = response_data['data'][0]['cost'] 
                return {'success': True, 'price': ongkir_value, 'error_message': False, 'warning_message': False}
            else:
                raise Exception(response_data.get('meta', {}).get('message', 'Error API'))

        except Exception as e:
            return {'success': False, 'price': 0.0, 'error_message': f"Gagal menghitung ongkir: {str(e)}", 'warning_message': False}