{
    'name': "WAF Website v40",
    'version': '1.0',
    'sequence': 1,
    'depends': [
        'base',
        'web',
        'auth_signup',
        'website',
    ],
    'author': "Dorevia",
    'category': 'Website',
    'description': """
    Nouveau site web WAF avec charte graphique unifiée
    """,
    'data': [
        'views/layouts/hero_layout.xml',
        'views/sections/content_section.xml',
        'views/sections/footer_section.xml',
        'views/main_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # SCSS
            'waf_wo4/static/src/scss/layouts/_hero.scss',
            'waf_wo4/static/src/scss/main.scss',
        ],
        'web.assets_backend': [
        ],
    },
    'images': [
        'static/description/icon.png',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
} 