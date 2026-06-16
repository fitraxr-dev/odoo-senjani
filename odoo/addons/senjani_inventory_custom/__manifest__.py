{
    'name': 'Senjani Inventory',
    'version': '1.0',
    'category': 'Inventory/Delivery',
    'summary': 'Custom Delivery Carrier menggunakan API RajaOngkir Komerce',
    'depends': ['delivery', 'sale', 'senjani_odoo_core'],
    'auto_install': True,
    'data': [
        'views/delivery_carrier_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}