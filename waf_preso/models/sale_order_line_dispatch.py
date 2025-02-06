from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class SaleOrderLineDispatch(models.Model):
    _name = 'sale.order.line.dispatch'
    _description = 'Dispatch des lignes de commande'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    order_line_id = fields.Many2one(
        'sale.order.line',
        string='Ligne de commande',
        required=True,
        ondelete='cascade'
    )

    delivery_planning_ids = fields.One2many(
        'sale.order.line.dispatch.delivery',
        'dispatch_id',
        string='Livraisons planifiées'
    )

    order_id = fields.Many2one(
        'sale.order',
        string='Commande',
        related='order_line_id.order_id',
        store=True
    )

    product_id = fields.Many2one(
        'product.product',
        related='order_line_id.product_id',
        string='Produit',
        store=True
    )

    delivery_partner_id = fields.Many2one(
        'res.partner',
        string='Point de livraison',
        required=True,
        domain="[('id', 'in', allowed_delivery_partner_ids)]",
        tracking=True
    )

    allowed_delivery_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_allowed_delivery_partner_ids',
        store=True
    )

    shipping_address_id = fields.Many2one(
        'res.partner',
        string='Adresse de livraison',
        domain="[('parent_id', '=', delivery_partner_id)]",
        tracking=True
    )

    quantity = fields.Float(
        string='Quantité',
        required=True,
        tracking=True
    )

    date_dispatch = fields.Datetime(
        string='Date de dispatch',
        default=fields.Datetime.now,
        tracking=True
    )

    dispatched_qty = fields.Float(
        string='Quantité dispatchée',
        compute='_compute_dispatched_qty',
        store=True
    )

    remaining_qty = fields.Float(
        string='Quantité restante',
        compute='_compute_remaining_qty',
        store=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('done', 'Validé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', tracking=True)

    delivery_ids = fields.One2many(
        'sale.order.line.dispatch.delivery',
        'dispatch_id',
        string='Livraisons planifiées'
    )

    delivery_partner_ids = fields.Many2many(
        'res.partner',
        'sale_order_line_dispatch_delivery_rel',  # nom de table spécifique
        'dispatch_id',
        'partner_id',
        string='Points de livraison'
    )

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Ligne de commande',
        required=True,
        ondelete='cascade'
    )

    @api.depends('order_line_id.order_id.groupment_id.member_ids')
    def _compute_allowed_delivery_partner_ids(self):
        for dispatch in self:
            if dispatch.order_line_id.order_id.groupment_id:
                dispatch.allowed_delivery_partner_ids = dispatch.order_line_id.order_id.groupment_id.member_ids
            else:
                dispatch.allowed_delivery_partner_ids = self.env['res.partner']

    @api.depends('delivery_ids.quantity')
    def _compute_dispatched_qty(self):
        for record in self:
            record.dispatched_qty = sum(record.delivery_ids.mapped('quantity'))

    @api.depends('quantity', 'dispatched_qty')
    def _compute_remaining_qty(self):
        for record in self:
            record.remaining_qty = record.quantity - record.dispatched_qty

class SaleOrderLineDispatchDelivery(models.Model):
    _name = 'sale.order.line.dispatch.delivery'
    _description = 'Planification des livraisons'
    _order = 'scheduled_date'

    dispatch_id = fields.Many2one(
        'sale.order.line.dispatch',
        required=True,
        ondelete='cascade'
    )
    shipping_address_id = fields.Many2one(
        'res.partner',
        string="Adresse de livraison",
        domain="['|', ('parent_id', '=', dispatch_id.partner_id), ('id', '=', dispatch_id.partner_id)]",
        required=True
    )
    scheduled_date = fields.Datetime(
        string="Date prévue",
        required=True
    )
    quantity = fields.Float(
        string="Quantité à livrer",
        required=True
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string="Bon de livraison",
        readonly=True
    )
    state = fields.Selection([
        ('draft', 'Planifié'),
        ('picking_created', 'BL Créé'),
        ('delivered', 'Livré'),
        ('cancel', 'Annulé')
    ], default='draft')

    @api.constrains('quantity')
    def _check_quantity(self):
        for record in self:
            available = record.dispatch_id.quantity_remaining + record.quantity
            if record.quantity > available:
                raise ValidationError(_(
                    "La quantité à livrer ne peut pas dépasser la quantité restante à livrer.\n"
                    "Quantité disponible : %(qty)s",
                    qty=available
                ))

    def action_create_picking(self):
        """Crée le bon de livraison"""
        self.ensure_one()
        picking = self.env['stock.picking'].create(self._prepare_picking_values())
        self.write({
            'picking_id': picking.id,
            'state': 'picking_created'
        })
        return picking

    def _prepare_picking_values(self):
        """Prépare les valeurs pour la création du picking"""
        order = self.dispatch_id.order_line_id.order_id
        return {
            'partner_id': self.dispatch_id.partner_id.id,
            'picking_type_id': order.warehouse_id.out_type_id.id,
            'location_id': order.warehouse_id.lot_stock_id.id,
            'location_dest_id': self.shipping_address_id.property_stock_customer.id,
            'scheduled_date': self.scheduled_date,
            'origin': f"{order.name}/DISP/{self.dispatch_id.id}/DEL/{self.id}",
            'move_ids': [(0, 0, {
                'name': self.dispatch_id.order_line_id.name,
                'product_id': self.dispatch_id.order_line_id.product_id.id,
                'product_uom_qty': self.quantity,
                'product_uom': self.dispatch_id.order_line_id.product_uom.id,
                'location_id': order.warehouse_id.lot_stock_id.id,
                'location_dest_id': self.shipping_address_id.property_stock_customer.id,
            })]
        }