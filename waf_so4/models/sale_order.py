from odoo import api, fields, models, _
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'portal.mixin']
    _description = 'Sales Order with Dispatch'

    def _compute_access_url(self):
        super()._compute_access_url()
        for order in self:
            order.access_url = '/my/orders/%s' % order.id

    transaction_ids = fields.Many2many(
        'payment.transaction',
        'sale_order_dispatch_transaction_rel',
        'sale_order_id',
        'transaction_id',
        string='Transactions',
        copy=False,
        readonly=True
    )

    tag_ids = fields.Many2many(
        'crm.tag',
        'sale_order_dispatch_tag_rel',
        'sale_order_id',
        'tag_id',
        string='Tags'
    )

    delivery_mode = fields.Selection([
        ('standard', 'Standard'),
        ('dispatch', 'Dispatch')
    ], string='Delivery Mode', default='standard')

    dispatch_id = fields.One2many('sale.dispatch', 'sale_order_id', string='Dispatch')

    dispatch_ids = fields.One2many(
        'sale.dispatch',
        'sale_order_id',
        string='Dispatches'
    )

    active_dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Current Dispatch',
        compute='_compute_active_dispatch'
    )

    dispatch_percent = fields.Float(
        string='Dispatch Progress',
        compute='_compute_dispatch_percent',
        store=True,
        help="Percentage of dispatched quantities"
    )

    dispatch_percent_global = fields.Float(
        string='Global Dispatch Progress',
        compute='_compute_dispatch_percent_global',
        store=True,
        help="Global percentage of dispatched quantities",
        digits=(5, 2)
    )

    picking_count_from_dispatch = fields.Integer(
        string='Delivery Orders from Dispatch',
        compute='_compute_picking_count_from_dispatch'
    )

    dispatch_line_count = fields.Integer(
        string='Dispatch Lines Count',
        compute='_compute_dispatch_line_count'
    )

    def action_confirm(self):
        """Override order confirmation."""
        if self.delivery_mode == 'dispatch':
            res = super().action_confirm()
            self.picking_ids.unlink()
            return res
        return super().action_confirm()

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Override to prevent picking creation in dispatch mode."""
        if self.delivery_mode == 'dispatch' or self.env.context.get('skip_delivery'):
            _logger.info("Dispatch mode active - No automatic delivery order creation.")
            return True
        return super()._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)

    def _create_delivery(self):
        """Prevent automatic delivery order creation in dispatch mode."""
        if self.delivery_mode == 'Dispatch' or self.env.context.get('skip_delivery'):
            _logger.info("Dispatch mode active - No automatic delivery order creation.")
            return False
        return super()._create_delivery()

    def action_create_dispatch(self):
        """Create a new dispatch."""
        self.ensure_one()
        return {
            'name': _('Create Dispatch'),
            'view_mode': 'form',
            'res_model': 'sale.dispatch',
            'type': 'ir.actions.act_window',
            'context': {
                'default_sale_order_id': self.id,
                'default_mandator_id': self.partner_id.id,
            },
        }
    
    def action_show_dispatch(self):
        """Display the current dispatch."""
        self.ensure_one()
        dispatch = self.env['sale.dispatch'].search([
            ('sale_order_id', '=', self.id)
        ], limit=1)
        
        if not dispatch:
            raise UserError(_("No dispatch found for this order."))
            
        return {
            'name': _('Show Dispatch'),
            'view_mode': 'form',
            'res_model': 'sale.dispatch',
            'type': 'ir.actions.act_window',    
            'res_id': dispatch.id,
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_add_dispatch(self):
        """Open the current dispatch."""
        self.ensure_one()
        if not self.active_dispatch_id:
            return self.action_create_dispatch()
            
        return {
            'name': _('Add to Dispatch'),
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

    @api.depends('dispatch_ids.picking_ids')
    def _compute_picking_count_from_dispatch(self):
        for order in self:
            order.picking_count_from_dispatch = len(order.dispatch_ids.picking_ids)

    def action_view_dispatch_pickings(self):
        """Display delivery orders linked to dispatches."""
        self.ensure_one()
        pickings = self.dispatch_ids.picking_ids
        action = {
            'name': _('Dispatch Delivery Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', pickings.ids)],
        }
        if len(pickings) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': pickings.id,
            })
        return action

    @api.depends('dispatch_ids.line_ids')
    def _compute_dispatch_line_count(self):
        for order in self:
            order.dispatch_line_count = len(order.dispatch_ids.line_ids)

    def action_view_dispatch_lines(self):
        """Display dispatch lines."""
        self.ensure_one()
        return {
            'name': _('Dispatch Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.line.dispatch',
            'view_mode': 'tree,form',
            'domain': [('dispatch_id', 'in', self.dispatch_ids.ids)],
        }
