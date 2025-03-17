from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    address_ids = fields.Many2many(
        'partner.address',
        'partner_address_rel',
        column1='partner_id',
        column2='address_id',
        string='Delivery Addresses'
    )

    dispatch_line_ids = fields.One2many(
        'sale.line.dispatch',
        'stakeholder_id',
        string='Dispatch Lines',
        help="Dispatch lines where this partner is stakeholder"
    )

    hide_main_company = fields.Boolean(
        string="Hide Main Company Info on Documents",
        default=False
    )
    hide_company_on = fields.Selection([
        ('all', 'All Documents'),
        ('delivery', 'Delivery Documents Only'),
        ('invoice', 'Invoices Only'),
    ], string="Hide Company Info On", 
    default='all',
    help="Select on which type of documents the main company information should be hidden") 