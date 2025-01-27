{
    "name": "Watergile Localisation ISO",
    "version": "1.0.0",
    "summary": "Gestion des zones, divisions et lieux géographiques selon les normes ISO 3166 et 19115",
    "description": """
        Module de gestion des localisations conformes aux normes ISO 3166 et 19115:
        - Zones géographiques personnalisables
        - Divisions administratives (ISO 3166-2)
        - Lieux et coordonnées géographiques (ISO 19115)

        Fonctionnalités:
        - Synchronisation avec les données ISO 3166-2
        - Synchronisation avec les données ISO 19115
        - Gestion des zones géographiques personnalisables
        - Gestion des divisions administratives (ISO 3166-2)
        - Gestion des lieux et coordonnées géographiques (ISO 19115)
    """,
    "author": "Dorevia",
    "category": "Base",
    "website": "https://www.doreviateam.com",
    "depends": [
        "base",
        'mail',
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_country_zone_views.xml",
        # "views/res_country_division_views.xml",
        # "views/res_country_place_views.xml",
        "views/menus.xml", 
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
