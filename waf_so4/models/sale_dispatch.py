from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class SaleDispatch(models.Model):
    _name = 'sale.dispatch'
    _description = 'Sale Dispatch'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'

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
    ], string='Status', default='draft', required=True, tracking=True)

    # Doit être géré à la ligne de dispatch
    # scheduled_date = fields.Date(
    #     string='Date de livraison',
    #     required=True,
    #     tracking=True,
    #     default=fields.Date.context_today
    # )

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

    # Garder un seul champ pour le progrès
    dispatch_progress = fields.Float(
        string='Progress',
        compute='_compute_progress',
        store=True
    )

    # Renommer l'étiquette pour éviter le conflit
    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Default Shipping Address',  # Changé de 'Delivery Address' à 'Default Shipping Address'
        help="Default shipping address for this dispatch. Can be overridden at line level."
    )

    # Supprimer ces champs car ils sont gérés au niveau des lignes
    # delivery_address_id = fields.Many2one('partner.address', string='Delivery Address')
    product_id = fields.Many2one('product.product', string='Product')
    product_uom_qty = fields.Float(string='Quantity')
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    stakeholder_id = fields.Many2one('res.partner', string='Stakeholder')
    scheduled_date = fields.Date(string='Scheduled Date')

    _sql_constraints = [
        ('unique_sale_order', 'unique(sale_order_id)', 'A sale order can only have one dispatch!')
    ]

    @api.depends('line_ids.state')
    def _compute_progress(self):
        for dispatch in self:
            if not dispatch.line_ids:
                dispatch.dispatch_progress = 0.0
                continue
            
            total_lines = len(dispatch.line_ids)
            done_lines = len(dispatch.line_ids.filtered(lambda l: l.state == 'done'))
            dispatch.dispatch_progress = (done_lines / total_lines) * 100 if total_lines > 0 else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.dispatch') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        for dispatch in self:
            if dispatch.state != 'draft':
                raise UserError(_("Only draft dispatches can be confirmed."))
            dispatch.line_ids.action_confirm()
            dispatch.write({'state': 'confirmed'})

    def action_done(self):
        for dispatch in self:
            if dispatch.state != 'confirmed':
                raise UserError(_("Only confirmed dispatches can be marked as done."))
            dispatch.line_ids.action_done()
            dispatch.write({'state': 'done'})

    def action_cancel(self):
        for dispatch in self:
            if dispatch.state in ['done']:
                raise UserError(_("Done dispatches cannot be cancelled."))
            dispatch.line_ids.action_cancel()
            dispatch.write({'state': 'cancel'})

    def action_draft(self):
        for dispatch in self:
            if dispatch.state != 'cancel':
                raise UserError(_("Only cancelled dispatches can be set back to draft."))
            dispatch.line_ids.action_draft()
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
        if self.sale_order_id and self.sale_order_id.commitment_date:
            self.commitment_date = self.sale_order_id.commitment_date

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