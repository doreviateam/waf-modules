{
    'name': 'Watergile Partner',
    'version': '1.0',
    'category': 'Hidden',
    'sequence': 1,
    'summary': 'Extension des partenaires pour la gestion de groupes',
    'description': """
        Extension du module res.partner pour gérer :
        - Maison mère
        - Sièges
        - Antennes
        - Filiales
        - Blaz et organisation
        - Badges et hiérarchie
        - Localisation française
    """,
    'author': 'Dorevia',
    'website': 'https://www.doreviateam.com',
    'depends': [
        'base',
        'contacts',
        'hr',
        'watergile_core',
        'web',                 # Pour les widgets web
    ],
    'data': [
        # Sécurité uniquement
        'security/watergile_security.xml',
        'security/ir.model.access.csv',
        
        # Vue de test
        'views/res_partner_test.xml',
        'views/partner_blaz.xml',
        'views/partner_badge.xml',
        'views/partner_location.xml',
        'views/menu.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}