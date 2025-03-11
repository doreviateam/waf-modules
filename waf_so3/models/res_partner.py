from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    address_ids = fields.One2many(
        'partner.address',
        'main_partner_id',
        string='Adresses de livraison'
    )

    dispatch_line_ids = fields.One2many(
        'sale.line.dispatch',
        'stakeholder_id',
        string='Lignes de dispatch',
        help="Lignes de dispatch où ce partenaire est stakeholder"
    ) 