{
    'name': 'Senjani Delivery',
    'version': '1.0',
    'category': 'Inventory/Delivery',
    'summary': 'Custom Delivery Carrier menggunakan API RajaOngkir Komerce',
    'depends': ['delivery', 'sale'],
    'data': [
        'views/delivery_carrier_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}