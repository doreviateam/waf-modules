{
    'name': "WAF Website v31",
    'version': '1.0',
    'sequence': 50,
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
        'security/ir.model.access.csv',
        'views/snippets/footer.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # CSS
            'waf_wo31/static/src/lib/bootstrap-icons/bootstrap-icons.min.css',
            'waf_wo31/static/src/lib/aos/aos.css',
            'waf_wo31/static/src/scss/style.scss',
            # JS
            'waf_wo31/static/src/lib/aos/aos.js',
            'waf_wo31/static/src/js/main.js',
        ],
        'web.assets_backend': [
            # Bootstrap et variables
            ('include', 'web._assets_bootstrap'),
            
            # Nos fichiers SCSS
            'waf_wo31/static/src/scss/variables.scss',
            'waf_wo31/static/src/scss/main.scss',
            'waf_wo31/static/src/scss/login.scss',
            'waf_wo31/static/src/scss/style.scss',
            'waf_wo31/static/src/scss/snippets/s_footer.scss',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
} 