from odoo import api, fields, models, _
from odoo.tools import float_compare

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    dispatch_required = fields.Boolean(
        string='Dispatch requis',
        default=False,
        help="Indique si cette ligne nécessite un dispatch"
    )

    dispatch_ids = fields.One2many(
        'sale.line.dispatch',
        'sale_order_line_id',
        string='Dispatches',
        copy=False
    )

    dispatch_state = fields.Selection([
        ('no_dispatch', 'Pas de dispatch'),
        ('to_dispatch', 'À dispatcher'),
        ('partial', 'Partiellement dispatché'),
        ('dispatched', 'Dispatché'),
        ('error', 'Erreur')
    ], string='État du dispatch', 
       compute='_compute_dispatch_state',
       store=True
    )

    remaining_qty_to_dispatch = fields.Float(
        string='À dispatcher',
        compute='_compute_remaining_qty_to_dispatch',
        store=True,
        help="Quantité restante à dispatcher"
    )

    @api.depends('dispatch_required', 'product_uom_qty', 'dispatch_ids.quantity', 'dispatch_ids.state')
    def _compute_remaining_qty_to_dispatch(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if not line.dispatch_required:
                line.remaining_qty_to_dispatch = 0.0
                continue

            dispatched_qty = sum(
                dispatch.quantity 
                for dispatch in line.dispatch_ids 
                if dispatch.state != 'cancel'
            )
            line.remaining_qty_to_dispatch = line.product_uom_qty - dispatched_qty

    @api.depends('dispatch_required', 'remaining_qty_to_dispatch', 'product_uom_qty')
    def _compute_dispatch_state(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if not line.dispatch_required:
                line.dispatch_state = 'no_dispatch'
                continue

            if not line.dispatch_ids:
                line.dispatch_state = 'to_dispatch'
            elif line.remaining_qty_to_dispatch == line.product_uom_qty:
                line.dispatch_state = 'to_dispatch'
            elif line.remaining_qty_to_dispatch > 0:
                line.dispatch_state = 'partial'
            elif line.remaining_qty_to_dispatch == 0:
                line.dispatch_state = 'dispatched'
            else:
                line.dispatch_state = 'error'

    @api.onchange('dispatch_required')
    def _onchange_dispatch_required(self):
        if not self.dispatch_required:
            if self.dispatch_ids:
                return {
                    'warning': {
                        'title': _('Attention'),
                        'message': _('Impossible de désactiver le dispatch car des dispatches existent déjà.')
                    }
                }
            self.dispatch_state = 'no_dispatch'
        else:
            if self.product_id.type not in ['product', 'consu']:
                return {
                    'warning': {
                        'title': _('Attention'),
                        'message': _('Seuls les produits stockables ou consommables peuvent être dispatchés.')
                    }
                }
            self.dispatch_state = 'to_dispatch'

    def action_view_dispatches(self):
        """Action pour afficher les dispatches associés."""
        return {
            'name': _('Dispatches'),
            'view_mode': 'tree,form',
            'res_model': 'sale.line.dispatch',
            'type': 'ir.actions.act_window',
            'domain': [('sale_order_line_id', '=', self.id)],
            'context': {'default_sale_order_line_id': self.id},
        } 