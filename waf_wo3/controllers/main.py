# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

class WafWo3Controller(http.Controller):
    @http.route('/', type='http', auth="public", website=True)
    def index(self, **kw):
        return request.render('waf_wo3.waf_wo3_homepage')

    @http.route(['/contact'], type='http', auth="public", website=True)
    def contact(self, **kwargs):
        return request.render('website.contactus')