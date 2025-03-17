from odoo import http
from odoo.http import request

class WafController(http.Controller):
    @http.route('/', type='http', auth="public", website=True)
    def index(self, **kw):
        return request.render('waf_wo31.waf_homepage')

    @http.route('/demo', type='http', auth="public", website=True)
    def demo(self, **kw):
        return request.render('waf_wo31.demo_page')  # Template à créer plus tard

    @http.route('/contact', type='http', auth="public", website=True)
    def contact(self, **kw):
        return request.render('waf_wo31.contact_page')  # Template à créer plus tard