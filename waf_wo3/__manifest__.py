{
    'name': 'WAF WO3',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Website Addons Features',
    'sequence': 1,
    'author': 'Dorevia',
    'website': 'https://www.dorevia.com',
    'depends': [
        'base',
        'mail',  # Déplacé avant website car c'est une dépendance de base
        'website',
        'website_sale',
        'website_blog',
        'portal',
        # 'website_form',
        # 'website_form_project',
        # 'website_crm',
        # 'website_partner',
        # 'website_mail',
        # 'website_menu',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/templates.xml',
        'views/snippets/snippets.xml',
        'views/snippets/s_header.xml',
        'views/snippets/s_footer.xml',
        'data/website_data.xml',
        'data/website_pages.xml',
        'data/mail_template.xml',
  

        # Reports


        # Views
        'views/snippets/s_contact_form.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            '/waf_wo3/static/src/css/style.css',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
