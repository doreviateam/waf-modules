from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class SaleDispatch(models.Model):
    _name = 'sale.dispatch'
    _description = 'Sale Dispatch'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'
    _sql_constraints = [
        ('unique_sale_order_dispatch', 
         'UNIQUE(sale_order_id)',
         'Une commande ne peut avoir qu\'un seul dispatch.')
    ]

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', compute='_compute_state', store=True, default='draft', tracking=True)

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        depends=['sale_order_id.currency_id'],
        store=True,
        string='Currency'
    )

    current_dispatch_progress = fields.Float(
        string='Current Dispatch Progress',
        compute='_compute_current_dispatch_progress',
        store=True,
        help="Percentage of quantities in this dispatch"
    )

    global_dispatch_progress = fields.Float(
        string='Global Dispatch Progress',
        compute='_compute_global_dispatch_progress',
        store=True,
        help="Global percentage of dispatched quantities across all dispatches",
        digits=(5, 2)
    )

    line_ids = fields.One2many(
        'sale.line.dispatch',
        'dispatch_id',
        string='Dispatch Lines'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='sale_order_id.company_id',
        store=True
    )

    picking_ids = fields.Many2many(
        'stock.picking',
        string='Delivery Orders',
        copy=False,
        readonly=True
    )

    picking_count = fields.Integer(
        string='Delivery Orders Count',
        compute='_compute_picking_count'
    )

    mandator_id = fields.Many2one(
        'res.partner',
        string='Mandator',
        required=True
    )

    commitment_date = fields.Datetime(
        string='Commitment Date',
        tracking=True,
        help="This is the delivery date promised to the customer"
    )

    dispatch_progress = fields.Float(
        string='Progress',
        compute='_compute_dispatch_progress',
        store=True,
        help="Percentage of delivered quantities based on stock moves"
    )

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Default Shipping Address',
        help="Default shipping address for this dispatch. Can be overridden at line level."
    )

    product_id = fields.Many2one('product.product', string='Product')
    product_uom_qty = fields.Float(string='Quantity')
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    stakeholder_id = fields.Many2one('res.partner', string='Stakeholder')
    scheduled_date = fields.Date(string='Scheduled Date')

    stakeholder_ids = fields.Many2many(
        'res.partner',
        'sale_dispatch_stakeholder_rel',
        'dispatch_id',
        'mandator_id',
        string='Stakeholders',
        domain="[('is_company', '=', True)]",
        help="Liste des partenaires concernés par ce dispatch",
        copy=True,
        required=True
    )

    @api.depends('picking_ids', 'picking_ids.state')
    def _compute_state(self):
        for dispatch in self:
            if dispatch.state == 'cancel':
                continue
            elif not dispatch.picking_ids:
                dispatch.state = 'draft'
            elif all(p.state == 'done' for p in dispatch.picking_ids):
                dispatch.state = 'done'
            else:
                dispatch.state = 'confirmed'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.dispatch') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        """Confirm the dispatch and create pickings."""
        self.ensure_one()
        if self.picking_ids:
            raise UserError(_("This dispatch already has delivery orders."))
            
        if self.sale_order_id.state not in ['sale', 'done']:
            raise UserError(_("The sales order must be confirmed before confirming the dispatch."))

        # Create pickings for each stakeholder and delivery address combination
        picking_vals_by_group = {}
        
        for line in self.line_ids:
            key = (line.stakeholder_id.id, line.partner_shipping_id.id, line.scheduled_date)
            if key not in picking_vals_by_group:
                picking_vals_by_group[key] = {
                    'partner_id': line.stakeholder_id.id,
                    'partner_shipping_id': line.partner_shipping_id.id,
                    'picking_type_id': self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1).id,
                    'location_id': self.env['stock.location'].search([('usage', '=', 'internal')], limit=1).id,
                    'location_dest_id': self.env['stock.location'].search([('usage', '=', 'customer')], limit=1).id,
                    'origin': f"{self.sale_order_id.name}/{self.name}",
                    'scheduled_date': line.scheduled_date,
                    'move_ids': [],
                    'company_id': self.company_id.id,
                }
            
            move_vals = {
                'name': f"{self.sale_order_id.name}/{self.name}: {line.product_id.name}",
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.product_uom_qty,
                'location_id': picking_vals_by_group[key]['location_id'],
                'location_dest_id': picking_vals_by_group[key]['location_dest_id'],
                'sale_line_id': line.sale_order_line_id.id,
                'company_id': self.company_id.id,
                'date': line.scheduled_date,
            }
            picking_vals_by_group[key]['move_ids'].append((0, 0, move_vals))

        # Create pickings
        pickings = self.env['stock.picking']
        for picking_vals in picking_vals_by_group.values():
            picking = pickings.create(picking_vals)
            pickings |= picking

        self.picking_ids = pickings
        return True

    @api.constrains('state', 'sale_order_id')
    def _check_confirmation_requirements(self):
        """Vérifie que le dispatch ne peut être confirmé que si la commande est confirmée."""
        for dispatch in self:
            if dispatch.state == 'confirmed' and dispatch.sale_order_id.state not in ['sale', 'done']:
                raise ValidationError(_("Un dispatch ne peut être confirmé que si la commande liée est confirmée."))

    def action_done(self):
        """Mark dispatch as done based on pickings state."""
        for dispatch in self:
            if dispatch.state != 'confirmed':
                raise UserError(_("Only confirmed dispatches can be marked as done."))
                
            if not all(picking.state == 'done' for picking in dispatch.picking_ids):
                raise UserError(_("All delivery orders must be done to mark the dispatch as done."))
            
            dispatch.write({'state': 'done'})

    def action_cancel(self):
        for dispatch in self:
            if any(p.state == 'done' for p in dispatch.picking_ids):
                raise UserError(_("Cannot cancel a dispatch with completed deliveries."))
            dispatch.picking_ids.action_cancel()
            dispatch.write({'state': 'cancel'})

    def action_draft(self):
        for dispatch in self:
            if dispatch.state != 'cancel':
                raise UserError(_("Only cancelled dispatches can be set back to draft."))
            if dispatch.picking_ids:
                raise UserError(_("Cannot reset to draft a dispatch with existing delivery orders."))
            dispatch.write({'state': 'draft'})

    def action_view_pickings(self):
        """Display associated delivery orders."""
        self.ensure_one()
        return {
            'name': _('Delivery Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'context': {'create': False},
        }

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for dispatch in self:
            dispatch.picking_count = len(dispatch.picking_ids)

    @api.constrains('sale_order_id')
    def _check_sale_order(self):
        """Check if the order is linked to dispatch delivery mode."""
        for dispatch in self:
            if dispatch.sale_order_id.delivery_mode != 'dispatch':
                raise ValidationError(_(
                    "The order must be configured for dispatch delivery mode."
                ))

    @api.constrains('line_ids')
    def _check_lines(self):
        """Check if there is at least one dispatch line."""
        for dispatch in self:
            if not dispatch.line_ids:
                raise ValidationError(_("A dispatch must have at least one line."))

    @api.depends('line_ids.product_uom_qty', 'sale_order_id.order_line.product_uom_qty')
    def _compute_current_dispatch_progress(self):
        for dispatch in self:
            total_qty = sum(dispatch.sale_order_id.order_line.mapped('product_uom_qty'))
            dispatched_qty = sum(dispatch.line_ids.mapped('product_uom_qty'))
            dispatch.current_dispatch_progress = (dispatched_qty / total_qty * 100) if total_qty else 0.0

    @api.onchange('sale_order_id')
    def _onchange_sale_order(self):
        """Met à jour les stakeholders depuis la commande."""
        if self.sale_order_id:
            self.stakeholder_ids = [(6, 0, self.sale_order_id.stakeholder_ids.ids)]

    @api.constrains('stakeholder_ids')
    def _check_stakeholders(self):
        """Vérifie qu'il y a au moins un partenaire concerné."""
        for dispatch in self:
            if not dispatch.stakeholder_ids:
                raise ValidationError(_("Un dispatch doit avoir au moins un partenaire concerné."))

    def write(self, vals):
        res = super().write(vals)
        if 'commitment_date' in vals:
            for record in self:
                record.sale_order_id.write({
                    'commitment_date': vals['commitment_date']
                })
        return res

    @api.constrains('line_ids', 'sale_order_id')
    def _check_total_dispatch_quantity(self):
        for dispatch in self:
            # Group lines by order line
            lines_by_order_line = {}
            for line in dispatch.line_ids:
                if line.state != 'cancel':
                    if line.sale_order_line_id not in lines_by_order_line:
                        lines_by_order_line[line.sale_order_line_id] = 0
                    lines_by_order_line[line.sale_order_line_id] += line.product_uom_qty

            # Check each order line
            for order_line, total_qty in lines_by_order_line.items():
                if total_qty > order_line.product_uom_qty:
                    raise ValidationError(_(
                        "Total dispatched quantity (%(dispatched)s) cannot exceed "
                        "ordered quantity (%(ordered)s) for product %(product)s.",
                        dispatched=total_qty,
                        ordered=order_line.product_uom_qty,
                        product=order_line.product_id.display_name
                    ))

    @api.constrains('stakeholder_id')
    def _check_partner_shipping(self):
        return True

    @api.depends('sale_order_id.order_line.dispatched_qty', 'sale_order_id.order_line.product_uom_qty')
    def _compute_global_dispatch_progress(self):
        for dispatch in self:
            order = dispatch.sale_order_id
            if not order or not order.order_line:
                dispatch.global_dispatch_progress = 0.0
                continue

            total_qty = sum(order.order_line.mapped('product_uom_qty'))
            if not total_qty:
                dispatch.global_dispatch_progress = 0.0
                continue

            dispatched_qty = sum(order.order_line.mapped('dispatched_qty'))
            dispatch.global_dispatch_progress = min(100.0, (dispatched_qty / total_qty) * 100)

    def action_create_delivery(self):
        """Crée les bons de livraison groupés par date/stakeholder."""
        self.ensure_one()
        
        # 1. Récupérer les lignes confirmées
        lines = self.line_ids.filtered(lambda l: l.state == 'confirmed')
        if not lines:
            raise UserError(_("No confirmed lines to deliver."))

        # ... reste du code de action_create_delivery ...

    def _prepare_picking_values(self, scheduled_date, lines):
        """Prépare les valeurs pour la création du bon de livraison groupé."""
        # ... code de _prepare_picking_values ...

class SaleDispatchLine(models.Model):
    _name = 'sale.dispatch.line'
    _description = 'Sale Dispatch Line'

    dispatch_id = fields.Many2one('sale.dispatch', string='Dispatch', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_qty = fields.Float(string='Quantity', required=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', required=True)