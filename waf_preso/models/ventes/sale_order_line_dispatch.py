"""
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round

class SaleOrderLineDispatch(models.Model):
    _name = 'sale.order.line.dispatch'
    _description = 'Ligne de répartition des commandes'
    _order = 'dispatch_date, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    order_id = fields.Many2one(
        'sale.order',
        string='Commande',
        required=True,
        ondelete='cascade',
        tracking=True,
    )

    delivery_id = fields.Many2one(
        'stock.picking',
        string='Livraison',
        copy=False,
        tracking=True,
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Transfert',
        copy=False,
        tracking=True,
    )

    order_line_id = fields.Many2one(
        'sale.order.line',
        string='Ligne de commande',
        required=True,
        ondelete='cascade',
        tracking=True,
        domain="[('is_active', '=', True), ('is_groupment_order', '=', True)]"
    )

    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True,
        tracking=True,
    )

    product_uom_qty = fields.Float(
        string='Quantité',
        required=True,
        default=1.0,
        tracking=True,
    )

    product_uom = fields.Many2one(
        'uom.uom',
        string='Unité de mesure',
        required=True,
        tracking=True,
    )

    dispatch_date = fields.Date(
        string='Date de répartition',
        required=True,
        tracking=True,
    )

    note = fields.Text(
        string='Notes',
        tracking=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
        related='order_id.partner_id'
    )

    # Ajout des champs mandant et mandataire
    mandant_id = fields.Many2one(
        'res.partner',
        related='order_id.mandant_id',
        store=True,
        string='Société mandante'
    )

    mandataire_id = fields.Many2one(
        'res.partner',
        related='order_id.mandataire_id',
        store=True,
        string='Mandataire'
    )

    quantity = fields.Float(
        string='Quantité',
        required=True,
        tracking=True
    )

    ordered_qty = fields.Float(
        related='order_line_id.product_uom_qty',
        string='Quantité commandée'
    )

    delivered_qty = fields.Float(
        string='Quantité livrée',
        compute='_compute_delivered_qty',
        store=True
    )

    remaining_qty = fields.Float(
        string='Quantité restante',
        compute='_compute_remaining_qty',
        store=True
    )

    date_planned = fields.Date(
        string='Date prévue',
        required=True,
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé'),
    ], string='État', default='draft', required=True, tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company
    )

    delivery_ids = fields.One2many(
        'sale.order.line.dispatch.delivery',
        'dispatch_id',
        string='Livraisons'
    )

    delivery_count = fields.Integer(
        string='Nombre de livraisons',
        compute='_compute_delivery_count',
        store=True
    )

    price_unit = fields.Float(
        string='Prix unitaire',
        related='order_line_id.price_unit',
        readonly=True,
        store=True
    )

    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Devise',
        readonly=True,
        store=True,
    )

    delivery_date = fields.Date(
        string='Date de livraison',
        required=True
    )

    # Champs calculés
    @api.depends('delivery_ids.delivered_qty')
    def _compute_delivered_qty(self):
        for record in self:
            record.delivered_qty = sum(record.delivery_ids.mapped('delivered_qty'))

    @api.depends('quantity', 'delivered_qty')
    def _compute_remaining_qty(self):
        for record in self:
            record.remaining_qty = record.quantity - record.delivered_qty

    @api.depends('delivery_ids')
    def _compute_delivery_count(self):
        for record in self:
            record.delivery_count = len(record.delivery_ids)

    # Contraintes
    @api.constrains('product_uom_qty')
    def _check_quantity(self):
        for record in self:
            if record.product_uom_qty <= 0:
                raise ValidationError(_('La quantité doit être supérieure à 0.'))

    @api.constrains('quantity', 'order_line_id')
    def _check_quantity_total(self):
        for record in self:
            total_dispatched = self.search([
                ('order_line_id', '=', record.order_line_id.id),
                ('id', '!=', record.id),
                ('state', '!=', 'cancelled')
            ]).mapped('quantity')
            total_dispatched = sum(total_dispatched) + record.quantity
            if float_compare(total_dispatched, record.order_line_id.product_uom_qty, 2) > 0:
                raise ValidationError(_(
                    "La quantité totale dispatchée ne peut pas dépasser "
                    "la quantité commandée"
                ))

    # Méthodes CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.order.line.dispatch') or _('New')
        return super().create(vals_list)

    # Actions
    def action_confirm(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'confirmed'

    def action_done(self):
        for record in self:
            if record.state == 'confirmed':
                record.state = 'done'

    def action_cancel(self):
        for record in self:
            if record.state in ['draft', 'confirmed']:
                record.state = 'cancel'

    def action_draft(self):
        for record in self:
            if record.state == 'cancel':
                record.state = 'draft'

    def action_view_deliveries(self):
        self.ensure_one()
        return {
            'name': _('Livraisons'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.line.dispatch.delivery',
            'view_mode': 'tree,form',
            'domain': [('dispatch_id', '=', self.id)],
            'context': {'default_dispatch_id': self.id},
        }

    # Méthodes de validation
    def _check_can_start_delivery(self):
        for record in self:
            if not record.delivery_ids:
                raise UserError(_("Ajoutez au moins une livraison planifiée"))

    def _check_can_mark_done(self):
        for record in self:
            if float_compare(record.delivered_qty, record.quantity, precision_rounding=0.01) != 0:
                raise UserError(_("Les quantités livrées ne correspondent pas"))

    def _check_can_cancel(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_("Impossible d'annuler un dispatch terminé"))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id.id


class SaleOrderLineDispatchDelivery(models.Model):
    _name = 'sale.order.line.dispatch.delivery'
    _description = 'Livraison de la répartition'
    _rec_name = 'dispatch_id'

    dispatch_id = fields.Many2one(
        'sale.order.line.dispatch',
        string='Répartition',
        required=True,
        ondelete='cascade'
    )

    delivered_qty = fields.Float(
        string='Quantité livrée',
        default=0.0,
        required=True
    )

    delivery_date = fields.Date(
        string='Date de livraison',
        default=fields.Date.context_today
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('done', 'Livré'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', required=True)


