from odoo import fields, models

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    partner_ids = fields.Many2many(
        'res.partner',
        'product_pricelist_allowed_partner_rel',
        'pricelist_id',
        'partner_id',
        string='Partenaires autorisés',
        help="Partenaires autorisés à utiliser cette liste de prix"
    )

    delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        string='Zones de livraison',
        help='Zones de livraison où cette liste de prix est applicable',
    ) 
    