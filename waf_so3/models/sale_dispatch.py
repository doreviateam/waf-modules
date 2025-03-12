from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class SaleDispatch(models.Model):
    _name = 'sale.dispatch'
    _description = 'Sale Order Dispatch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', 
       default='draft',
       tracking=True)

    # Doit être géré à la ligne de dispatch
    # scheduled_date = fields.Date(
    #     string='Date de livraison',
    #     required=True,
    #     tracking=True,
    #     default=fields.Date.context_today
    # )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Order',
        required=True,
        domain="[('delivery_mode', '=', 'dispatch')]"
    )

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        depends=['sale_order_id.currency_id'],
        store=True,
        string='Currency'
    )

    dispatch_percent_global = fields.Float(
        string='Global Dispatch Progress',
        related='sale_order_id.dispatch_percent_global',
        store=True,
        help="Global percentage of dispatched quantities",
        digits=(5, 2)
    )

    dispatch_progress = fields.Float(
        string='Progress',
        compute='_compute_dispatch_progress',
        store=True,
        help="Global percentage of dispatched quantities"
    )

    line_ids = fields.One2many(
        'sale.line.dispatch',
        'dispatch_id',
        string='Lines'
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

    # Champ calculé pour l'adresse de livraison (optionnel maintenant)
    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Delivery Address',
        readonly=True,  # Maintenant en lecture seule car géré par les lignes
        help="Shown for information only. Delivery addresses are managed at line level."
    )

    _sql_constraints = [
        ('unique_sale_order', 
         'UNIQUE(sale_order_id)',
         'Only one dispatch is allowed per order!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de create."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.dispatch') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        """Confirm the dispatch."""
        for dispatch in self:
            if dispatch.state != 'draft':
                raise UserError(_("Only draft dispatches can be confirmed."))
            dispatch.write({'state': 'confirmed'})
            _logger.info(f"Dispatch {dispatch.name} confirmed.")

    def action_done(self):
        """Mark the dispatch as done."""
        for dispatch in self:
            if dispatch.state != 'confirmed':
                raise UserError(_("Only confirmed dispatches can be marked as done."))
            dispatch.write({'state': 'done'})
            _logger.info(f"Dispatch {dispatch.name} marked as done.")

    def action_cancel(self):
        """Cancel the dispatch."""
        for dispatch in self:
            if dispatch.state not in ['draft', 'confirmed']:
                raise UserError(_("Only draft or confirmed dispatches can be cancelled."))
            dispatch.write({'state': 'cancel'})
            _logger.info(f"Dispatch {dispatch.name} cancelled.")

    def action_draft(self):
        """Set the dispatch back to draft."""
        for dispatch in self:
            if dispatch.state != 'cancel':
                raise UserError(_("Only cancelled dispatches can be set back to draft."))
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
    def _compute_dispatch_progress(self):
        for dispatch in self:
            total_qty = sum(dispatch.sale_order_id.order_line.mapped('product_uom_qty'))
            dispatched_qty = sum(dispatch.line_ids.mapped('product_uom_qty'))
            dispatch.dispatch_progress = (dispatched_qty / total_qty * 100) if total_qty else 0.0

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