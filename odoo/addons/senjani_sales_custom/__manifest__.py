{
    'name': 'Senjani Sales Custom',
    'version': '18.0.1.0',
    'summary': 'Customizations for Sales and Invoicing workflows',
    'author': 'Tim Senjani',
    'license': 'LGPL-3',
    'category': 'Sales/Sales',
    'depends': ['sale', 'account', 'senjani_website_custom'],
    'data': [
        'views/sale_order_views.xml',
        'views/sale_make_invoice_advance_views.xml',
        'views/sale_menus.xml',
    ],
    'installable': True,
    'application': True,
}
