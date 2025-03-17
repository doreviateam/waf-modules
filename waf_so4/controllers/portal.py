from odoo import http
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.http import request

class CustomerPortalInherit(CustomerPortal):
    def _prepare_orders_domain(self, partner):
        domain = super()._prepare_orders_domain(partner)
        return domain

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        partner = request.env.user.partner_id

        SaleOrder = request.env['sale.order']
        order_count = SaleOrder.search_count([
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', 'in', ['sale', 'done'])
        ])

        values['sale_order_count'] = order_count
        return values