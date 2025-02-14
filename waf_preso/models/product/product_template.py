from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    PRODUCT_TYPES = [
        ('consu', 'Consommable'),
        ('service', 'Service'),
        ('product', 'Produit stockable')
    ]

    hs_code = fields.Char(
        string="HS Code",
        help="Code HS du produit",
        tracking=True)
    
    country_of_origin = fields.Many2one(
        'res.country', 
        string='Pays d\'origine', 
        tracking=True)

    delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        string='Zones de livraison',
        help='Zones de livraison où ce produit peut être livré',
        tracking=True)

    @api.constrains('detailed_type', 'type')
    def _check_product_type(self):
        for product in self:
            if product.type != product.detailed_type:
                raise ValidationError(_("Le type de ce produit ne correspond pas au type détaillé"))

    @api.onchange('type')
    def _onchange_type(self):
        """Synchronise automatiquement le type détaillé avec le type général"""
        if self.type:
            self.detailed_type = self.type
