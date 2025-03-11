from odoo import api, fields, models, _

class StockMove(models.Model):
    _inherit = 'stock.move'

    dispatch_id = fields.Many2one('sale.line.dispatch', string='Dispatch', ondelete='set null')

    def _prepare_merge_moves_distinct_fields(self):
        """Ajoute dispatch_id aux champs distincts lors de la fusion des mouvements."""
        distinct_fields = super()._prepare_merge_moves_distinct_fields()
        distinct_fields.append('dispatch_id')
        return distinct_fields

    def _prepare_merge_move_sort_method(self):
        """Ajoute dispatch_id aux clés de tri lors de la fusion des mouvements."""
        keys_sorted = super()._prepare_merge_move_sort_method()
        keys_sorted.append('dispatch_id.id')
        return keys_sorted 