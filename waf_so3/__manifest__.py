{
    'name': 'WAF SO3',
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
        'sale_management',
        'sale_stock',
        'stock',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        
        # Data
        'data/ir_sequence_data.xml',
        'data/bobinette_data.xml',
        'data/move_5000_data.xml',
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
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
