from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
from itertools import groupby
from operator import itemgetter

_logger = logging.getLogger(__name__)

class SaleLineDispatch(models.Model):
    _name = 'sale.line.dispatch'
    _description = 'Dispatch Line'
    _rec_name = 'display_name'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    state = fields.Selection(
        related='dispatch_id.state',
        store=True,
        readonly=True)

    dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Dispatch',
        required=True,
        ondelete='cascade'
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Order',
        related='dispatch_id.sale_order_id',
        store=True,
        readonly=True
    )

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Order Line',
        required=True,
        domain="[('order_id', '=', sale_order_id), ('remaining_qty', '>', 0)]"
    )

    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Delivery Address',
        required=True,
        domain="[]"
    )

    product_id = fields.Many2one(
        'product.product',
        related='sale_order_line_id.product_id',
        store=True
    )

    product_uom = fields.Many2one(
        'uom.uom',
        related='sale_order_line_id.product_uom',
        string='Unit',
        store=True
    )

    product_uom_qty = fields.Float(
        string='Quantity',
        required=True,
        tracking=True,
        copy=False
    )

    price_unit = fields.Float(
        related='sale_order_line_id.price_unit',
        string='Unit Price',
        store=True
    )

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        store=True
    )

    company_id = fields.Many2one(
        'res.company',
        related='sale_order_id.company_id',
        store=True
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id'
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order',
        copy=False
    )

    stakeholder_id = fields.Many2one(
        'res.partner',
        string='Stakeholder',
        required=True,
        tracking=True,
        default=lambda self: self.sale_order_id.partner_id,
        domain="[('is_company', '=', True)]",  # B2B only
        help="Stakeholder benefiting from the order"
    )

    scheduled_date = fields.Date(
        string='Delivery Date',
        required=True,
        tracking=True,
        default=fields.Date.context_today
    )

    def action_view_picking(self):
        """Display the associated delivery order."""
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No delivery order is associated with this line."))
            
        return {
            'name': _('Delivery Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'context': {'create': False},
        }

    def action_confirm(self):
        # Regrouper les lignes par adresse de livraison et date
        def groupby_key(line):
            return (line.delivery_address_id.id, line.scheduled_date, line.sale_order_id.id)
        
        # Trier les lignes pour assurer un regroupement correct
        sorted_lines = self.sorted(key=lambda l: (l.delivery_address_id.id, l.scheduled_date, l.sale_order_id.id))
        
        for (address_id, scheduled_date, order_id), lines in groupby(sorted_lines, key=groupby_key):
            lines = list(lines)  # Convertir l'itérateur en liste
            if not lines:
                continue

            first_line = lines[0]
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('warehouse_id.company_id', '=', first_line.sale_order_id.company_id.id)
            ], limit=1)

            # Créer la commande de livraison pour le groupe
            picking_vals = {
                'partner_id': first_line.delivery_address_id.main_partner_id.id,
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'scheduled_date': scheduled_date,
                'origin': first_line.sale_order_id.name,
                'move_ids': [],
            }

            # Ajouter les mouvements pour chaque ligne
            for line in lines:
                picking_vals['move_ids'].append((0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'location_id': picking_type.default_location_src_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id,
                    'sale_line_id': line.sale_order_line_id.id,
                }))

            # Créer la commande de livraison et la lier aux lignes
            picking = self.env['stock.picking'].create(picking_vals)
            lines_to_update = self.browse([l.id for l in lines])
            lines_to_update.write({
                'picking_id': picking.id,
                'state': 'confirmed'
            })

    def action_done(self):
        """Mark the dispatch line as done."""
        for line in self:
            if line.state != 'confirmed':
                raise UserError(_("Only confirmed lines can be marked as done."))
            line.write({'state': 'done'})
            _logger.info(f"Dispatch line {line.display_name} marked as done.")

    def action_cancel(self):
        """Cancel the dispatch line."""
        for line in self:
            if line.state not in ['draft', 'confirmed']:
                raise UserError(_("Only draft or confirmed lines can be cancelled."))
            line.write({'state': 'cancel'})
            _logger.info(f"Dispatch line {line.display_name} cancelled.")

    def action_draft(self):
        """Set the line back to draft."""
        for line in self:
            if line.state != 'cancel':
                raise UserError(_("Only cancelled lines can be set back to draft."))
            line.write({'state': 'draft'})
            _logger.info(f"Dispatch line {line.display_name} set back to draft.")

    @api.depends('dispatch_id.name', 'sale_order_line_id.product_id.name')
    def _compute_name(self):
        for line in self:
            if line.dispatch_id and line.sale_order_line_id:
                line.name = f"{line.dispatch_id.name}/{line.sale_order_line_id.product_id.name}"
            else:
                line.name = "/"

    @api.depends('product_id', 'delivery_address_id', 'product_uom_qty')
    def _compute_display_name(self):
        for line in self:
            parts = []
            if line.product_id:
                parts.append(line.product_id.name)
            if line.product_uom_qty:
                parts.append(str(line.product_uom_qty))
            if line.delivery_address_id:
                parts.append(line.delivery_address_id.display_name)
            line.display_name = " - ".join(filter(None, parts)) or "/"

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        self.sale_order_line_id = False
        self.delivery_address_id = False

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id(self):
        if self.sale_order_line_id:
            initial_qty = self.sale_order_line_id.product_uom_qty
            
            # Calculer le total des lignes existantes et nouvelles
            total_dispatched = 0
            
            # Lignes déjà enregistrées
            domain = [
                ('sale_order_line_id', '=', self.sale_order_line_id.id),
                ('state', 'not in', ['cancel']),
                ('id', '!=', self._origin.id)
            ]
            total_dispatched += sum(self.search(domain).mapped('product_uom_qty'))
            
            # Lignes éditées dans la même commande de livraison
            if self.dispatch_id:
                for line in self.dispatch_id.line_ids:
                    if (line.sale_order_line_id == self.sale_order_line_id 
                        and line.id != self._origin.id 
                        and not line.state == 'cancel'):
                        total_dispatched += line.product_uom_qty
            
            remaining_qty = initial_qty - total_dispatched
            
            if not self.product_uom_qty:
                self.product_uom_qty = max(0, remaining_qty)

    @api.constrains('product_uom_qty')
    def _check_quantity(self):
        for line in self:
            if line.product_uom_qty <= 0:
                raise ValidationError(_("Quantity must be greater than 0."))

    @api.constrains('partner_id', 'delivery_address_id')
    def _check_delivery_address(self):
        return True

    @api.constrains('sale_order_line_id', 'sale_order_id')
    def _check_sale_order_line(self):
        """Check if the line belongs to the selected order."""
        for dispatch in self:
            if dispatch.sale_order_line_id.order_id != dispatch.sale_order_id:
                raise ValidationError(_(
                    "The order line must belong to the selected order."
                ))

    @api.constrains('product_uom_qty', 'sale_order_line_id')
    def _check_dispatch_quantity(self):
        for line in self:
            # Calculer le total des quantités en cours et confirmées
            domain = [
                ('sale_order_line_id', '=', line.sale_order_line_id.id),
                ('state', 'not in', ['cancel']),
                ('id', '!=', line.id)  # Exclure la ligne actuelle
            ]
            
            other_lines_qty = sum(self.search(domain).mapped('product_uom_qty'))
            total_qty = other_lines_qty + line.product_uom_qty
            
            if total_qty > line.sale_order_line_id.product_uom_qty:
                available_qty = line.sale_order_line_id.product_uom_qty - other_lines_qty
                raise ValidationError(_(
                    "Total dispatched quantity (%(total)s) cannot exceed "
                    "ordered quantity (%(ordered)s) for product %(product)s.\n"
                    "Available quantity: %(available)s",
                    total=total_qty,
                    ordered=line.sale_order_line_id.product_uom_qty,
                    available=max(0, available_qty),
                    product=line.product_id.display_name
                ))

    def _check_company_delivery_address(self):
        return True

    @api.constrains('partner_id')
    def _check_partner_shipping(self):
        return True

    @api.constrains('delivery_address_id', 'partner_id')
    def _check_delivery_address_partner(self):
        return True

    @api.constrains('picking_id')
    def _check_picking_address(self):
        return True