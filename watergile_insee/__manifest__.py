{
    'name': 'WaterGile Insee',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': 'Synchronisation des données Insee',
    'description': """
        Synchronisation automatique des données entreprises avec l'API Insee.
""",
    'depends': [
        'base', 
        'contacts', 
        'watergile_partner'
    ],
    'data': [
        'security/watergile_security.xml',
        'security/ir.model.access.csv',
        'security/watergile_security.xml',
        'config/res_config_settings.xml',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        'views/insee_sync_views.xml',  # D'abord les vues avec les actions
        'views/res_partner_views.xml',
        'data/res_user_david_data.xml',
        'views/menus.xml',  # Ensuite les menus
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}