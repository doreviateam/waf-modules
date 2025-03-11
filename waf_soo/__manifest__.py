{
    'name': 'W.A.F SOO',
    'version': '17.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Gestion avancée des dispatches et livraisons',
    
    'description': """
Module de gestion avancée des dispatches et livraisons
===================================================================

Fonctionnalités principales
--------------------------
* Gestion des zones de livraison avec capacités et créneaux
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
    'maintainer': 'Dorevia Team',
    'website': 'https://www.dorevia.com',
    'license': 'LGPL-3',
    
    'depends': [
        # Modules techniques
        'base',
        'web',
        'mail',
        
        # Modules fonctionnels
        'contacts',
        'sale_management',
        'stock',
        'delivery',
        'purchase',
        'account',
        'product',
        'crm',
        'sale_stock',
    ],
    
    'data': [
        # Sécurité - Chargé en premier
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/model_access_rules.xml',

        # Données de configuration
        'data/ir_sequence.xml',

        # Vues métier (chargées en premier pour que les références soient disponibles)
        # 'views/tools/calendar_holiday_views.xml',
        # 'views/tools/calendar_region_views.xml',
        'views/product/product_views.xml',
        'views/dispatch/sale_line_dispatch_views.xml',
        'views/delivery/zone_views.xml',
        'views/delivery/carrier_views.xml',
        'views/sale/sale_order_views.xml',
        'views/stock/stock_picking_views.xml',
        'views/stock/stock_move_views.xml',
        'views/stock/stock_picking_type_views.xml',
        'views/partner/partner_address_views.xml',
        'views/partner/contact_views.xml',

        # Actions et menus (chargés après les vues)
        'views/common/action_views.xml',
        'views/common/menu_views.xml',

        # Rapports
        'report/report_deliveryslip.xml',

        # Données de démonstration
        'data/partner/credit_mutuel_data.xml',
        'data/partner/move_5000_data.xml',
        'data/partner/partner_address_data.xml',
        'data/sale/sale_order_data.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            # # CSS
            # 'waf_soo/static/src/scss/styles.scss',
            # # JavaScript
            # 'waf_soo/static/src/js/**/*.js',
            # # XML Templates
            # 'waf_soo/static/src/xml/**/*.xml',
        ],
    },

    'application': True,
    'installable': True,
    'auto_install': False,
    'sequence': 10,  # Position dans le menu des applications
    
    'external_dependencies': {
        'python': [
            'pandas>=2.0.0',
            'geopy>=2.4.0',
        ],
    },
}

