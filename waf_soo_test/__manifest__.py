{
    'name': 'WAF SOO Test',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Test module for WAF SOO',
    'description': """
        Test module for WAF SOO
    """,
    'author': 'Dorevia',
    'website': 'https://www.dorevia.com',
    'depends': [
        'sale',
        'stock',
        'mail',
    ],
    'data': [
        'views/sale_order_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
} 