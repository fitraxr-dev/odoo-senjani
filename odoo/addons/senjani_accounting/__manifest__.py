{
    'name': 'Senjani Accounting',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Modul Akuntansi Terintegrasi untuk Senjani E-Commerce',
    'description': """
        Modul akuntansi khusus Senjani yang mengintegrasikan:
        - Manajemen Invoice dari Xendit Payment (via Sales Order otomatis)
        - Manajemen Bill dari Purchase Order
        - Rekonsiliasi manual dengan mutasi bank BRI
        - Laporan keuangan lengkap (PDF): Ledger, Trial Balance, Balance Sheet, P&L, Tax
        - Laporan harian: Cash Book, Day Book, Bank Book
        - Fiscal Year & Lock Date
        - UI bersih — hanya fitur yang relevan yang ditampilkan
    """,
    'author': 'Tim Senjani',
    'license': 'LGPL-3',
    'depends': [
        # Accounting base
        'account',
        # 8 accounting addons yang sudah ada
        'accounting_pdf_reports',
        'om_account_accountant',
        'om_account_asset',
        'om_account_budget',
        'om_account_daily_reports',
        'om_account_followup',
        'om_fiscal_year',
        'om_recurring_payments',
        # ERP integration
        'sale_management',
        'purchase',
        'stock',
        'website_sale',
        'payment',
        # Communication
        'mail',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/account_payment_config.xml',
        'views/menu_hide.xml',
        'views/invoice_view.xml',
        'views/purchase_bill_view.xml',
        'views/dashboard.xml',
        'views/menu.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
