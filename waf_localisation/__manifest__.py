{
    'name': 'W.A.F Localisation',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': 'Outils de validation d\'adresses et de SIRET',
    'description': """
        Validation d'adresses françaises (BAN)
        Validation d'adresses internationales (OSM)
        Validation de SIRET (INSEE)
    """,
    'author': 'WAF Solution',
    'website': 'https://www.waf-solution.fr',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'waf_contacts',  # Ajouté pour l'intégration
    ],
    'external_dependencies': {
        'python': ['unidecode', 'requests'],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
