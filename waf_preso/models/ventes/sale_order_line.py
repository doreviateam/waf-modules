"""
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Champs techniques
    dispatch_enabled = fields.Boolean(
        string='Dispatch activé',
        compute='_compute_dispatch_enabled',
        store=True,
        index=True,
        help="Indique si le dispatch est possible pour cette ligne"
    )

    # Relations One2many
    dispatch_ids = fields.One2many(
        'sale.order.line.dispatch',
        'order_line_id',
        string='Répartitions'
    )

    # Relations Many2many
    delivery_partner_ids = fields.Many2many(
        'res.partner',
        'sale_order_line_delivery_partner_rel',  # Ajout d'un nom explicite
        'order_line_id',
        'partner_id',
        string='Partenaires de livraison',
        compute='_compute_delivery_partner_ids',
        store=True
    )

    # Quantités et suivi
    dispatched_quantity = fields.Float(
        string='Quantité répartie',
        compute='_compute_dispatched_quantity',
        store=True
    )

    remaining_qty = fields.Float(
        string='Quantité restante',
        compute='_compute_dispatch_quantities',
        store=True,
        digits='Product Unit of Measure',
        help="Quantité restante à dispatcher"
    )

    dispatch_count = fields.Integer(
        string='Nombre de dispatches',
        compute='_compute_dispatch_count',
        store=True
    )

    # États
    dispatch_state = fields.Selection([
        ('draft', "Non dispatché"),
        ('partial', "Partiellement dispatché"),
        ('done', "Entièrement dispatché")
    ],
        string='État du dispatch',
        compute='_compute_dispatch_state',
        store=True,
        index=True
    )

    # Calculs
    @api.depends('order_id.groupment_ids', 'product_id')
    def _compute_dispatch_enabled(self):
        for line in self:
            line.dispatch_enabled = bool(
                line.order_id.groupment_ids and 
                line.product_id.type in ['product', 'consu']
            )

    @api.depends('order_id.partner_id', 'order_id.partner_id.groupment_ids.partner_ids')
    def _compute_delivery_partner_ids(self):
        for line in self:
            partners = line.order_id.partner_id.groupment_ids.mapped('partner_ids')
            line.delivery_partner_ids = [(6, 0, partners.ids)]

    @api.depends('dispatch_ids.quantity', 'dispatch_ids.state', 'product_uom_qty')
    def _compute_dispatch_quantities(self):
        for line in self:
            valid_dispatches = line.dispatch_ids.filtered(
                lambda d: d.state not in ['cancelled']
            )
            line.dispatched_quantity = sum(valid_dispatches.mapped('quantity'))
            line.remaining_qty = line.product_uom_qty - line.dispatched_quantity

    @api.depends('dispatch_ids')
    def _compute_dispatch_count(self):
        for line in self:
            line.dispatch_count = len(line.dispatch_ids)

    @api.depends('dispatched_quantity', 'product_uom_qty')
    def _compute_dispatch_state(self):
        for line in self:
            if not line.dispatched_quantity:
                line.dispatch_state = 'draft'
            elif line.dispatched_quantity >= line.product_uom_qty:
                line.dispatch_state = 'done'
            else:
                line.dispatch_state = 'partial'

    # Contraintes
    @api.constrains('dispatch_ids', 'product_uom_qty')
    def _check_dispatch_quantities(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if float_compare(line.dispatched_quantity, line.product_uom_qty, precision_digits=precision) > 0:
                raise ValidationError(_(
                    "La quantité dispatchée ne peut pas dépasser la quantité commandée"
                ))

    # Actions
    def action_view_dispatches(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dispatches'),
            'res_model': 'sale.order.line.dispatch',
            'view_mode': 'tree,form',
            'domain': [('order_line_id', '=', self.id)],
            'context': {
                'default_order_line_id': self.id,
                'default_product_id': self.product_id.id,
                'search_default_draft': 1
            }
        }

    def action_create_dispatch(self):
        self.ensure_one()
        return {
            'name': _('Créer une répartition'),
            'type': 'ir.actions.act_window',
            'res_model': 'create.delivery.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.order_id.id,
                'default_order_line_id': self.id,
            }
        }

