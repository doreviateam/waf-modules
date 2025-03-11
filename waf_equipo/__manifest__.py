{
    'name': 'WAF EQUIPO',
    'version': '1.0',
    'category': 'Manufacturing',
    'summary': 'Gestion des équipements et pièces détachées',
    'description': """
        Module de gestion des équipements et pièces détachées.
        Fonctionnalités :
        - Gestion des équipements
        - Gestion des pièces détachées
        - Suivi des maintenances
        - Gestion des garanties
    """,
    'author': 'Dorevia',
    'website': 'https://www.dorevia.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'product',
        'stock',
        'waf_soo',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/equipment/equipment_views.xml',
        'views/equipment/spare_part_views.xml',
        'views/partner/partner_views.xml',
        'views/partner/partner_blaz_views.xml',
        'views/common/action_views.xml',
        'views/common/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
} 