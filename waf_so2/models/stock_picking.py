from odoo import api, fields, models, _

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    dispatch_id = fields.Many2one('sale.line.dispatch', string='Dispatch', ondelete='set null') 