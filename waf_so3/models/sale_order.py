from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_mode = fields.Selection([
        ('standard', 'Standard'),
        ('dispatch', 'Dispatch')
    ], string='Mode de livraison', default='standard', required=True)

    dispatch_ids = fields.One2many(
        'sale.dispatch',
        'sale_order_id',
        string='Dispatches'
    )

    active_dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Dispatch en cours',
        compute='_compute_active_dispatch'
    )

    dispatch_percent = fields.Float(
        string='Progression dispatch',
        compute='_compute_dispatch_percent',
        store=True,
        help="Pourcentage des quantités dispatchées"
    )

    dispatch_percent_global = fields.Float(
        string='Progression dispatch globale',
        compute='_compute_dispatch_percent_global',
        store=True,
        help="Pourcentage global des quantités dispatchées",
        digits=(5, 2)
    )

    def action_confirm(self):
        """Surcharge de la confirmation de commande."""
        if self.delivery_mode == 'dispatch':
            self.picking_ids.unlink()
            return self.write({'state': 'sale'})
        return super().action_confirm()

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Surcharge pour empêcher la création des pickings en mode dispatch."""
        if self.delivery_mode == 'dispatch' or self.env.context.get('skip_delivery'):
            _logger.info("Mode dispatch activé - Pas de création automatique du bon de livraison.")
            return True
        return super()._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)

    def _create_delivery(self):
        """Empêche la création automatique des BL en mode dispatch."""
        if self.delivery_mode == 'Dispatch' or self.env.context.get('skip_delivery'):
            _logger.info("Mode dispatch activé - Pas de création automatique du bon de livraison.")
            return False
        return super()._create_delivery()

    def action_create_dispatch(self):
        """Crée un nouveau dispatch."""
        self.ensure_one()
        return {
            'name': _('Créer Dispatch'),
            'view_mode': 'form',
            'res_model': 'sale.dispatch',
            'type': 'ir.actions.act_window',
            'context': {
                'default_sale_order_id': self.id,
                'default_stakeholder_id': self.partner_id.id,
            },
        }

    def action_add_dispatch(self):
        """Ouvre le dispatch en cours."""
        self.ensure_one()
        if not self.active_dispatch_id:
            return self.action_create_dispatch()
            
        return {
            'name': _('Ajouter au Dispatch'),
            'view_mode': 'form',
            'res_model': 'sale.dispatch',
            'type': 'ir.actions.act_window',
            'res_id': self.active_dispatch_id.id,
            'context': {'form_view_initial_mode': 'edit'},
        }

    @api.depends('order_line.dispatched_qty', 'order_line.product_uom_qty')
    def _compute_dispatch_percent(self):
        for order in self:
            if not order.order_line:
                order.dispatch_percent = 0.0
                continue

            total_qty = sum(order.order_line.mapped('product_uom_qty'))
            if not total_qty:
                order.dispatch_percent = 0.0
                continue

            dispatched_qty = sum(order.order_line.mapped('dispatched_qty'))
            order.dispatch_percent = min(100.0, (dispatched_qty / total_qty) * 100)

    @api.depends('dispatch_ids', 'dispatch_ids.state')
    def _compute_active_dispatch(self):
        for order in self:
            order.active_dispatch_id = order.dispatch_ids.filtered(
                lambda d: d.state == 'draft'
            )[:1]

    @api.depends('order_line.dispatched_qty', 'order_line.product_uom_qty')
    def _compute_dispatch_percent_global(self):
        for order in self:
            if not order.order_line:
                order.dispatch_percent_global = 0.0
                continue

            total_qty = sum(order.order_line.mapped('product_uom_qty'))
            if not total_qty:
                order.dispatch_percent_global = 0.0
                continue

            dispatched_qty = sum(order.order_line.mapped('dispatched_qty'))
            order.dispatch_percent_global = min(100.0, (dispatched_qty / total_qty) * 100)
