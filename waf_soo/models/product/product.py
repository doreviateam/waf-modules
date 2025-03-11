from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dispatchable = fields.Boolean(
        string='Peut être dispatché',
        default=True,
        help="Si coché, ce produit peut être dispatché dans une commande en mode dispatch"
    ) 