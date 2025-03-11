from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round
from datetime import datetime


class SaleOrderLine(models.Model):
    """
    """
    _inherit = 'sale.order.line'
    _description = 'Ligne de commande avec dispatch'
    _check_company_auto = True

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
    ], string='État du dispatch', compute='_compute_dispatch_state', store=True)

    remaining_qty_to_dispatch = fields.Float(
        string='Quantité restante à dispatcher',
        compute='_compute_remaining_qty_to_dispatch',
        store=True
    )

    @api.depends('product_uom_qty', 'dispatch_ids.quantity', 'dispatch_ids.state')
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
            line.remaining_qty_to_dispatch = float_round(
                line.product_uom_qty - dispatched_qty,
                precision_digits=precision
            )

    @api.depends('dispatch_required', 'remaining_qty_to_dispatch', 'product_uom_qty')
    def _compute_dispatch_state(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if not line.dispatch_required:
                line.dispatch_state = 'no_dispatch'
                continue

            if float_compare(line.remaining_qty_to_dispatch, line.product_uom_qty, 
                           precision_digits=precision) == 0:
                line.dispatch_state = 'to_dispatch'
            elif float_compare(line.remaining_qty_to_dispatch, 0, 
                             precision_digits=precision) > 0:
                line.dispatch_state = 'partial'
            elif float_compare(line.remaining_qty_to_dispatch, 0, 
                             precision_digits=precision) == 0:
                line.dispatch_state = 'dispatched'
            else:
                line.dispatch_state = 'error'

    def action_toggle_dispatch_required(self):
        """Toggle le besoin de dispatch sur la ligne."""
        for line in self:
            if line.dispatch_ids and line.dispatch_required:
                raise UserError(_("Impossible de désactiver le dispatch car des dispatches existent déjà."))
            line.dispatch_required = not line.dispatch_required

    @api.constrains('dispatch_ids', 'product_uom_qty')
    def _check_dispatch_quantity(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if float_compare(line.remaining_qty_to_dispatch, 0, 
                           precision_digits=precision) < 0:
                raise ValidationError(_(
                    "Dépassement de la quantité autorisée pour %(product)s",
                    product=line.product_id.display_name
                ))

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
