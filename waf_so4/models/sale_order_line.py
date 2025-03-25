from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ------------------
    # Fields Definition
    # ------------------
    # Relation fields
    dispatch_line_ids = fields.One2many(
        'sale.line.dispatch',
        'sale_order_line_id',
        string='Dispatch Lines'
    )

    # Computed fields
    dispatched_qty_line = fields.Float(
        string='Dispatched Quantity',
        compute='_compute_dispatch_quantity_line',
        store=True,
        help="Quantity already dispatched for this line"
    )

    remaining_qty_line = fields.Float(
        string='Remaining Quantity to Dispatch',
        compute='_compute_dispatch_quantity_line',
        store=True,
        help="Remaining quantity to dispatch"
    )

    dispatch_progress_line = fields.Float(
        string='Dispatch Progress',
        compute='_compute_dispatch_quantity_line',
        store=True,
        help="Percentage of dispatched quantity"
    )

    # ------------------------
    # Compute Methods
    # ------------------------
    @api.depends('product_uom_qty', 'dispatch_line_ids.state', 'dispatch_line_ids.product_uom_qty')
    def _compute_dispatch_quantity_line(self):
        """Calcule les quantités liées au dispatch pour chaque ligne"""
        for line in self:
            dispatched_qty = sum(
                line.dispatch_line_ids.filtered(
                    lambda l: l.state in ['draft', 'confirmed']
                ).mapped('product_uom_qty')
            )
            
            # Mise à jour des champs calculés
            line.update({
                'dispatched_qty_line': dispatched_qty,
                'remaining_qty_line': max(0.0, line.product_uom_qty - dispatched_qty),
                'dispatch_progress_line': min(
                    100.0, 
                    (dispatched_qty / line.product_uom_qty * 100.0) if line.product_uom_qty else 0.0
                )
            })

    # ------------------------
    # Onchange Methods
    # ------------------------
    @api.onchange('dispatch_line_ids')
    def _onchange_dispatch_lines(self):
        """Déclenche le recalcul des quantités lors des changements de dispatch"""
        self._compute_dispatch_quantity_line()
