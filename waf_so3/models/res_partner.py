from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    address_ids = fields.One2many(
        'partner.address',
        'main_partner_id',
        string='Delivery Addresses'
    )

    dispatch_line_ids = fields.One2many(
        'sale.line.dispatch',
        'stakeholder_id',
        string='Dispatch Lines',
        help="Dispatch lines where this partner is stakeholder"
    ) 