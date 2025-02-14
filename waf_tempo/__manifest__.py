{
    'name': 'W.A.F Tempo',
    'version': '1.0.0',
    'category': 'Technical Settings',
    'summary': 'Gestion avancée de la temporalité',
    'author': 'Dorevia',
    'website': 'https://www.doreviateam.com',
    'description': """
        Module technique fournissant des outils pour la gestion de la temporalité.

        Fonctionnalités :
        - Gestion des périodes
        - Gestion des jours ouvrés et des dates fériées
        - Support des calendriers nationaux via workalendar
    """,
    'depends': [
        'base',
        'mail',
    ],
    'external_dependencies': {
        'python': ['workalendar'],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/calendar_views.xml',

        # Data
        'data/calendar_region_data.xml',
        'data/calendar_holiday_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'visible': False,
    'license': 'LGPL-3',
}
