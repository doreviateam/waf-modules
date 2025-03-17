from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    dispatch_line_ids = fields.One2many(
        'sale.line.dispatch',
        'sale_order_line_id',
        string='Dispatch Lines'
    )

    dispatched_qty = fields.Float(
        string='Dispatched Quantity',
        compute='_compute_dispatch_quantities',
        store=True,
        help="Quantity already dispatched for this line"
    )

    remaining_qty = fields.Float(
        string='Remaining Quantity to Dispatch',
        compute='_compute_dispatch_quantities',
        store=True,
        help="Remaining quantity to dispatch"
    )

    dispatch_progress = fields.Float(
        string='Dispatch Progress',
        compute='_compute_dispatch_quantities',
        store=True,
        help="Percentage of dispatched quantity"
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