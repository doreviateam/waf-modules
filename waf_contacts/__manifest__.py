{
    'name': 'W.A.F Contacts',
    'version': '1.0.0',
    'depends': [ 
        'waf_core', 
        'contacts',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/region_views.xml',
        'data/res_country_state_regions.xml',
        'data/res_country_state_departments.xml',
        'views/res_partner_views.xml'
    ],
    'license': 'LGPL-3',
}
