{
    'name': 'WAF WO5',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Website Addon Framework',
    'description': """
        Website Addon Framework for Odoo 15.0
    """,
    'author': 'Doreviateam',
    'website': 'https://www.doreviateam.fr',
    'depends': [
        'base',
        'web',
        'website',
    ],
    'data': [
        'views/layouts/header_layout.xml',
        'views/layouts/hero_layout.xml',
        'views/layouts/main_layout.xml',
        'views/layouts/footer_layout.xml',
        'views/snippets/snippets.xml',
        'views/pages/home_page.xml',
        'views/pages/login.xml',
        'views/templates/main_template.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            'waf_wo5/static/src/scss/style.scss',
            'waf_wo5/static/src/js/header.js',
            ('include', 'https://unpkg.com/react@18/umd/react.production.min.js'),
            ('include', 'https://unpkg.com/react-dom@18/umd/react-dom.production.min.js'),
            'waf_wo5/static/src/components/Header.jsx',
        ],
    },

    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': True, 
    'auto_install': False,
    'website': True,
    'license': 'LGPL-3',
}