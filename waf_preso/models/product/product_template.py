from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    hs_code = fields.Char(string="HS Code", help="Code HS du produit")
    country_of_origin = fields.Many2one('res.country', string='Pays d\'origine', tracking=True)
    delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        string='Zones de livraison',
        help='Zones de livraison où ce produit peut être livré',
    )
