{
    'name': 'WAF Pre-SO',
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
        'account',
        'product',
        
        # Modules WAF
        'waf_core',
        'waf_contacts',
        'waf_localisation',
    ],
    
    'data': [
        # Sécurité
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Wizards (déplacé avant les vues)
        'wizards/create_delivery_wizard_views.xml',
        
        # Vues communes
        'views/common/action_views.xml',
        'views/common/menu_views.xml',
        
        # Vues partenaires
        'views/partner/partner_groupment_views.xml',
        'views/partner/partner_interest_views.xml',
        'views/partner/partner_interest_category_views.xml',
        'views/partner/res_partner_views.xml',
        
        # Vues ventes
        'views/sale/sale_order_views.xml',
        'views/sale/line_dispatch_views.xml',
        
        # Vues livraison
        'views/delivery/delivery_zone_views.xml',
        'views/delivery/delivery_config_views.xml',
        'views/delivery/dispatch_delivery_views.xml',
        
        # Vues produits
        'views/product/product_template_views.xml',
        'views/product/product_pricelist_views.xml',
        
        # Vues stock
        'views/stock/stock_move_views.xml',
        'views/stock/stock_picking_views.xml',
        
        # Data
        'data/product_data.xml',
        'data/partner_data.xml',
        'data/partner_interest_data.xml',
        'data/partner_groupment_data.xml',
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
        # 'post_init_hook': 'post_init_hook',
        # 'uninstall_hook': 'uninstall_hook',
    
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

