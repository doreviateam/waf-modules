from odoo import models, fields

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    use_existing_lots = fields.Boolean(
        'Use Existing Lots/Serial Numbers',
        default=False,
        help="If this is checked, you will be able to choose the Lots/Serial Numbers. You can also decide to not put lots in this operation type. This means it will create stock with no lot or not put a restriction on the lot taken."
    ) 