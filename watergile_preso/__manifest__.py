{
    'name': 'Watergile Preso',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Gestion des préparations de commandes',
    'description': """
        Module de gestion des préparations de commandes pour Watergile
    """,
    'depends': [
        'sale',
        'stock',
        'product',
        'watergile_partner',
        'watergile_web',
    ],
    'data': [
        'security/watergile_security.xml',
        'security/ir.model.access.csv',
        'views/delivery_views.xml',
        'views/sale_order_views.xml',
        'views/product_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}