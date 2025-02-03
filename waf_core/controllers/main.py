from odoo import http, SUPERUSER_ID
from odoo.addons.web.controllers.home import Home
from odoo.http import request

class WatergileHome(Home):
    @http.route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        response = super().web_login(redirect=redirect, **kw)
        
        if request.session.uid:
            user = request.env['res.users'].sudo().browse(request.session.uid)
            
            if request.session.uid == SUPERUSER_ID:
                return request.redirect('/web/superadmin/dashboard')
            elif user.has_group('waf_core.group_watergile_admin'):
                return request.redirect('/web/admin/dashboard')
            elif user.has_group('waf_core.group_watergile_manager'):
                return request.redirect('/web/manager/dashboard')
            elif user.has_group('waf_core.group_watergile_user'):
                return request.redirect('/web')
        
        return response

    @http.route('/web/superadmin/dashboard', type='http', auth='user')
    def superadmin_dashboard(self, **kw):
        if request.session.uid != SUPERUSER_ID:
            return request.redirect('/web')
        return request.render('waf_core.superadmin_dashboard')

    @http.route('/web/admin/dashboard', type='http', auth='user')
    def admin_dashboard(self, **kw):
        if not request.env.user.has_group('waf_core.group_watergile_admin'):
            return request.redirect('/web')
        return request.render('waf_core.admin_dashboard')

    @http.route('/web/manager/dashboard', type='http', auth='user')
    def manager_dashboard(self, **kw):
        if not request.env.user.has_group('waf_core.group_watergile_manager'):
            return request.redirect('/web')
        return request.render('waf_core.manager_dashboard')

class WatergileWeb(http.Controller):
    @http.route(['/web/admin/dashboard', '/web/superadmin/dashboard'], type='http', auth='user')
    def admin_dashboard(self, **kwargs):
        if not request.env.user.has_group('base.group_system'):
            return request.redirect('/web')
            
        values = {
            'user': request.env.user,
            'menu_data': request.env['ir.ui.menu'].load_menus(request.session.debug),
        }
        return request.render('waf_core.admin_dashboard', values)