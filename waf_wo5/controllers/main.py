from odoo import http
from odoo.http import request

class WafWebsite(http.Controller):
    @http.route('/', type='http', auth="public", website=True)
    def index(self, **kw):
        return request.render('waf_wo5.homepage')
