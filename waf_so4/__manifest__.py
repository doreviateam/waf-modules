{
    'name': 'WAF SO4',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Sales Dispatch Management',
    'description': """
        Sales Dispatch Management Module
    """,
    'author': 'Dorevia',
    'website': 'https://www.dorevia.com',
    'depends': [
        'base',
        'sale',
        'portal',
        'sale_pdf_quote_builder',
        'sale_management',
        'sale_stock',
        'stock',
        'contacts',
        'mail',
        'l10n_fr',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        
        # Data
        'data/ir_sequence_data.xml',
        'data/company_data.xml',
        'data/tax_data.xml',
        'data/bobinette_data.xml',
        'data/move_5000_data.xml',
        'data/reparation_service_data.xml',
        'data/client_data.xml',

        # Reports
        'reports/report_delivery_slip.xml',
        'reports/report_delivery_slip_valorised.xml',

        # Views
        'views/partner_address_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/sale_line_dispatch_views.xml',
        'views/sale_dispatch_views.xml',
        'views/stock_picking_views.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    
    'pre_init_hook': 'pre_init_hook',
}
