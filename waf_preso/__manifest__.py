{
    'name': 'WAF Pre-SO',  # Suppression du point dans le nom
    'version': '17.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Gestion des groupements d\'intérêt et livraisons multiples',
    
    # Description détaillée avec formatage RST
    'description': """
WAF Pre-SO
==========

Module de gestion des groupements d'intérêt et livraisons multiples pour Odoo 17.

Fonctionnalités
--------------
* Gestion complète des groupements d'intérêt
* Administration des mandataires et adhérents
* Configuration des livraisons multiples
* Système de dispatch des livraisons
* Fractionnement automatique des bons de commande
* Traçabilité avancée des colis
* Interface de reporting dédiée

Configuration
------------
* Paramétrage des groupements
* Définition des règles de livraison
* Configuration des workflows de validation
    """,

    # Informations techniques
    'author': 'Dorevia',
    'maintainers': ['Dorevia Team'],
    'website': 'https://www.doreviateam.com',
    'license': 'LGPL-3',
    
    # Dépendances essentielles
    'depends': [
        'base',
        'mail',
        'sale_management',
        'stock',
        # Modules WAF
        'waf_core',
        'waf_contacts',
        'waf_localisation',
        'waf_tempo',
    ],
    
    # Données
    'data': [
        # Sécurité (toujours en premier)
        'security/waf_preso_security.xml',
        'security/ir.model.access.csv',
        
        # Données de configuration
        'data/ir_sequence_data.xml',
        
        # Vues (ordre logique de chargement)
        'views/menu.xml',
        'views/partner_interest_views.xml',
        'views/partner_groupment_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',

        # Données de démonstration        
        'data/partner_interest_data.xml',
        'data/partner_groupment_data.xml',  
        'data/res_partner_data.xml',
        'data/product_data.xml',
    ],
    
    # Assets frontend et backend
    'assets': {
        'web.assets_backend': [
            # 'waf_preso/static/src/scss/groupment.scss',
            # 'waf_preso/static/src/js/groupment.js',
        ],
    },
    
    # Données de démonstration
    # 'demo': [
    #     'demo/partner_interest_demo.xml',
    #     'demo/res_partner_demo.xml',
    #     'demo/partner_groupment_demo.xml',
    # ],
    
    # Configuration Odoo 17
    'application': True,
    'installable': True,
    'auto_install': False,
    'sequence': 1,  # Position dans le menu des applications
    'development_status': 'Beta',
    
    # Métadonnées
    'version': '17.0.1.0.0',
    'currency': 'EUR',
    'price': 0.0,
    'images': ['static/description/banner.png'],
    
    # Hooks d'installation
    'pre_init_hook': None,
    'post_init_hook': None,
    'uninstall_hook': None,
}