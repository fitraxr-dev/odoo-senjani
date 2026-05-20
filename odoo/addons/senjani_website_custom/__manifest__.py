{
    'name': 'Senjani Website Custom',
    'summary': 'Custom frontend untuk katalog dan halaman detail produk Senjani',
    'description': 'Modul spesifik untuk implementasi desain e-commerce Senjani.',
    'author': 'Tim Senjani',
    'category': 'Website/Website',
    'version': '18.0.1.0',
    'depends': ['website_sale', 'website_sale_stock'],
    'data': [
        'views/products_item_templates.xml',
        'views/products_templates.xml',
        'views/pdp_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'senjani_website_custom/static/src/css/product_item_card.css',
            'senjani_website_custom/static/src/css/filter_drawer.css',
            'senjani_website_custom/static/src/css/product_reviews.css',
            'senjani_website_custom/static/src/xml/stock_availability.xml',
        ],
    },
    'application': False,
    'installable': True,
}