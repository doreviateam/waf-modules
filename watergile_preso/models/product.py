from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    need_dispatch = fields.Boolean(
        string='Nécessite un dispatch',
        help='Indique si le produit nécessite un dispatch',
        default=False
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _compute_need_dispatch(self):
        for product in self:
            product.need_dispatch = product.product_tmpl_id.need_dispatch

    need_dispatch = fields.Boolean(
        string='Nécessite un dispatch',
        compute='_compute_need_dispatch',
        store=True,
        related='product_tmpl_id.need_dispatch'
    )
