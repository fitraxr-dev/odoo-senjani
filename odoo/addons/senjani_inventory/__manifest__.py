{
    'name': 'Inventory Custom',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Kustomisasi modul inventory',
    'author': 'Tim Inventory Senjani',
    'license': 'LGPL-3',
    'depends': ['stock', 'delivery', 'base_address_extended'],
    'data': [
        'views/stock_picking_views.xml',
        'data/menu_hide.xml',
        'data/delivery_jne_data.xml',
    ],
    'installable': True,
    'auto_install': False,
}
