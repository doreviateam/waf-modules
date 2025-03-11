from odoo import fields, models, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    dispatch_id = fields.Many2one(
        'sale.line.dispatch',
        string='Dispatch',
        ondelete='set null'
    )

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        distinct_fields = super()._prepare_merge_moves_distinct_fields()
        distinct_fields.append('dispatch_id')
        return distinct_fields

    @api.model
    def _prepare_merge_move_sort_method(self, move):
        keys_sorted = super()._prepare_merge_move_sort_method(move)
        keys_sorted.append(move.dispatch_id.id)
        return keys_sorted

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
        return vals