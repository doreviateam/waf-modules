from odoo import api, fields, models, _

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'
    _description = 'Liste de prix produits avec restrictions groupements'

    groupment_ids = fields.Many2many(
        'partner.groupment',
        'product_pricelist_groupment_rel',
        'pricelist_id',
        'groupment_id',
        string='Groupements autorisés',
        tracking=True,
        help="Groupements de partenaires autorisés à utiliser cette liste de prix"
    )

    groupment_count = fields.Integer(
        string='Nombre de groupements',
        compute='_compute_groupment_count',
        store=True
    )

    @api.depends('groupment_ids')
    def _compute_groupment_count(self):
        for pricelist in self:
            pricelist.groupment_count = len(pricelist.groupment_ids)

    delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        string='Zones de livraison',
        help='Zones de livraison où cette liste de prix est applicable',
    ) 
    