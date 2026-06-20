{
    'name': 'Senjani Accounting',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Integrated Accounting Module for Senjani E-Commerce',
    'description': """
        Custom Senjani accounting module that integrates:
        - Invoice Management from Xendit Payment (via automatic Sales Orders)
        - Bill Management from Purchase Orders
        - Manual reconciliation with Bank Statements
        - Complete financial reports (PDF): Ledger, Trial Balance, Balance Sheet, P&L, Tax
        - Daily reports: Cash Book, Day Book, Bank Book
        - Fiscal Year & Lock Date
        - Clean UI — only relevant features displayed
    """,
    'author': 'Senjani Team',
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
        # Core
        'senjani_odoo_core',
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
        'wizard/bank_reconcile_wizard_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'senjani_accounting/static/src/js/journal_dashboard_graph.js',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': True,
    'images': ['static/description/icon.png'],
}
