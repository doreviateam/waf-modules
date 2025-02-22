{
    'name': 'W.A.F SOO',
    'version': '17.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Gestion avancée des groupements et livraisons',
    
    'description': """
Module de gestion avancée des groupements d'intérêt et des livraisons
===================================================================

Fonctionnalités principales
--------------------------
* Gestion des zones de livraison avec capacités et créneaux
* Gestion hiérarchique des groupements de partenaires
* Centres d'intérêt catégorisés avec statistiques
* Planification optimisée des livraisons
* Dispatch intelligent des commandes
* Tableaux de bord et rapports analytiques

Intégration
-----------
* Synchronisation avec la gestion commerciale
* Interface avec la logistique
* Connexion avec la comptabilité
* API REST pour intégrations externes

Sécurité
--------
* Gestion fine des droits d'accès
* Traçabilité complète des opérations
* Protection des données sensibles
""",

    'author': 'Dorevia',
    'maintainers': ['Dorevia Team'],
    'website': 'https://www.dorevia.com',
    'license': 'LGPL-3',
    
    'depends': [
        # Modules de base Odoo
        'base',
        'mail',
        'web',
        'base_setup',
        
        # Modules métier Odoo
        'contacts',
        'sale',
        'sale_management',
        'stock',
        'delivery',
        'purchase',
        'om_account_accountant',
        'account',
        'product',
        'crm',
        
        # Modules WAF
        'waf_core',
        'waf_contacts',
        'waf_localisation',
        'waf_transpo',
        'waf_tempo',
    ],
    
    'data': [        
        # Sécurité de base
        'security/security.xml',

        # Données
        'data/ir_sequence.xml',

        # Vues
        'views/dispatch/sale_line_dispatch_views.xml',
        'views/delivery/zone_views.xml',
        'views/sale/sale_order_views.xml',
        'views/delivery/carrier_views.xml',
        'views/stock/stock_picking_views.xml',
        'views/stock/stock_move_views.xml',
        'views/tools/calendar_holiday_views.xml',
        'views/tools/calendar_region_views.xml',
        'views/partner/contact_views.xml',
        'views/common/action_views.xml',
        'views/common/menu_views.xml',

        # Droits d'accès
        'security/ir.model.access.csv',
        'security/model_access_rules.xml',

        # Données de démonstration
        'data/partner/credit_mutuel_data.xml',
        'data/partner/move_5000_data.xml',
        'data/sale/sale_order_data.xml',
    ],
    
    'assets': {
        'web.assets_backend': [],
        'web.assets_qweb': [],
    },
    
    'demo': [],
    'images': [],

    'application': True,
    'installable': True,
    'auto_install': False,
    'sequence': 1,
    
    # Configuration
        'post_init_hook': None,
        'uninstall_hook': None,
    
    # Métadonnées
    'version': '17.0.1.0.0',
    'currency': 'EUR',
    'price': 0.0,
    'development_status': 'Beta',
    
    # Configuration technique
    'external_dependencies': {
        'python': [
            'pandas',
            'geopy',
        ],
    },
}

