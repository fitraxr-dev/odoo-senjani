{
    'name': 'Senjani Odoo Core',
    'summary': 'Core module containing shared models, fields, configurations, and core logic for Senjani ERP.',
    'description': 'Base core module for all custom Senjani extensions to ensure proper dependency management and avoid circular references.',
    'author': 'Tim Senjani',
    'license': 'LGPL-3',
    'category': 'Hidden',
    'version': '18.0.1.0',
    'depends': ['sale', 'stock', 'delivery', 'account'],
    'data': [],
    'application': True,
    'installable': True,
}
