{
    'name': 'W.A.F Core',
    'version': '17.0.1.0.0',
    'summary': 'Core module for W.A.F applications',
    'description': """
        Core module for WAF applications
        ===============================
        - Base configuration
        - Common mixins
        - Shared utilities
    """,
    'author': 'Dorevia',
    'category': 'Services/Project',
    'depends': [
        # Modules de base
        'base',
        'base_setup',
        'bus',
        'web',
        
        # Modules comptables et français
        'l10n_fr',
        'l10n_fr_fec',
        'account',
        'om_account_accountant',
        
        # Modules projet et vente
        'project',
        'hr_timesheet',
        'analytic',
        'product',
        'sale',
        'sale_management',
        'sale_timesheet',
        'sale_project',
        
        # Modules interface OCA
        'web_responsive',
        'web_notify',
        'web_dialog_size',
        'web_timeline',
        'web_tree_dynamic_colored_field',
        'web_chatter_position',
        'web_m2x_options',
    ],
    'data': [
        'views/webclient_templates.xml',
        'views/dashbord_templates.xml',
        'views/dashbord_actions.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/waf_core/static/src/scss/watergile_style.scss',
            '/waf_core/static/src/scss/chatter.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}