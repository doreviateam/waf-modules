{
    'name': 'WAF Transporteur',
    'version': '1.0',
    'category': 'Inventory/Delivery',
    'summary': 'Extensions des transporteurs pour WAF',
    'description': """
        Extensions des modules de transport pour WAF avec :
        - Mondial Relay
        - La Poste (à venir)
        - FedEx (à venir)
        
        Fonctionnalités :
        - Gestion des zones de livraison
        - Intégration avec le planning de livraison
        - Personnalisation par transporteur
    """,
    'depends': [
        'delivery_mondialrelay',
        # 'delivery_laposte',  # TODO: Ajouter les modules de livraison
        # 'delivery_fedex',    # TODO: Ajouter les modules de livraison
        # 'waf_preso',
    ],
    'data': [
        'views/mondial_relay/carrier_views.xml',
        # 'views/laposte/carrier_views.xml',    # TODO: Ajouter les vues
        # 'views/fedex/carrier_views.xml',      # TODO: Ajouter les vues
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
