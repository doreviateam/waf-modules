from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    dispatch_line_ids = fields.One2many(
        'sale.line.dispatch',
        'sale_order_line_id',
        string='Lignes de dispatch'
    )

    dispatched_qty = fields.Float(
        string='Quantité dispatchée',
        compute='_compute_dispatch_quantities',
        store=True,
        help="Quantité déjà dispatchée pour cette ligne"
    )

    remaining_qty = fields.Float(
        string='Quantité restante à dispatcher',
        compute='_compute_dispatch_quantities',
        store=True,
        help="Quantité restante à dispatcher"
    )

    dispatch_progress = fields.Float(
        string='Progression dispatch',
        compute='_compute_dispatch_quantities',
        store=True,
        help="Pourcentage de la quantité dispatchée"
    )

    @api.depends('product_uom_qty', 'dispatch_line_ids.state', 'dispatch_line_ids.product_uom_qty')
    def _compute_dispatch_quantities(self):
        for line in self:
            # Ne compter que les lignes non annulées
            valid_dispatches = line.dispatch_line_ids.filtered(lambda l: l.state != 'cancel')
            dispatched = sum(valid_dispatches.mapped('product_uom_qty'))
            
            line.dispatched_qty = dispatched
            line.remaining_qty = max(0.0, line.product_uom_qty - dispatched)
            line.dispatch_progress = min(100.0, (dispatched / line.product_uom_qty * 1.0) if line.product_uom_qty else 0.0)