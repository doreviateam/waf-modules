from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SparePart(models.Model):
    _inherit = 'product.template'
    _description = 'Pièce détachée'

    allowed_equipment_ids = fields.Many2many(
        'equipment',
        'product_equipment_rel',
        'product_id',
        'equipment_id',
        string='Équipements associés',
        tracking=True
    )

    is_spare_part = fields.Boolean(string='Pièce détachée',
                                   compute='_compute_is_spare_part',
                                   store=True)
    categ_id_name = fields.Char(string='Catégorie', compute='_compute_categ_id_name')

    @api.depends('categ_id', 'is_spare_part')
    def _compute_categ_id_name(self):
        for part in self:
            if part.categ_id and part.is_spare_part:
                part.categ_id_name = part.categ_id.name
            else:
                part.categ_id_name = '-'

    @api.depends('allowed_equipment_ids')
    def _compute_is_spare_part(self):
        for part in self:
            if len(part.allowed_equipment_ids) > 0:
                part.is_spare_part = True
            else:
                part.is_spare_part = False

   