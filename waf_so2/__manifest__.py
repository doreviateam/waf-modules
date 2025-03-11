{
    'name': 'WAF SO2',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Gestion avancée des commandes clients',
    'description': """
        Module de gestion avancée des commandes clients avec :
        - Mode de livraison dispatch
        - Gestion des adresses de livraison multiples
        - Suivi des dispatches
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
        'purchase_stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizards/dispatch_group_wizard_views.xml',
        'views/sale_dispatch_group_views.xml',
        'views/sale_line_dispatch_views.xml',
        'views/sale_order_views.xml',
        'views/partner_address_views.xml',
        'wizards/mass_dispatch_wizard_views.xml',

        # Demo
        'data/move_5000_data.xml',
        'data/bobinette_tpe.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
} 