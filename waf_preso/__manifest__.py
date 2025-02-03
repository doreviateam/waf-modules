{
    'name': 'W.A.F Pre-SO',
    'version': '17.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Gestion des groupements d\'intérêt et livraisons multiples',
    'description': """
Gestion des groupements d'intérêt et livraisons multiples
=======================================================

Fonctionnalités principales :
----------------------------
* Gestion des groupements d'intérêt
* Mandataires et adhérents
* Livraisons multiples
* Dispatch des livraisons
* Split des bons de commande
* Suivi des colis
    """,
    'author': 'Dorevia',
    'website': 'https://www.doreviateam.com',
    'depends': [
        'base',
        'sale_management',
        'stock',
        'mail',
        'waf_tempo',
        'waf_localisation',
        'waf_contacts',
        'waf_core',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv', 
        'views/res_partner_interest_type_views.xml',
        'views/res_partner_interest_groupment_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'development_status': 'Development',
    'maintainers': ['Dorevia'],
}