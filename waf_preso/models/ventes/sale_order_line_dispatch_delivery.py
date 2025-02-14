"""
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round

class SaleOrderLineDispatchDelivery(models.Model):
    _name = 'sale.order.line.dispatch.delivery'
    _description = 'Livraison de répartition de ligne de commande'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'dispatch_id'
    _order = 'delivery_date, id'

    # Champs de base
    dispatch_id = fields.Many2one(
        'sale.order.line.dispatch',
        string='Répartition',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    delivered_qty = fields.Float(
        string='Quantité livrée',
        default=0.0,
        required=True,
        tracking=True
    )

    delivery_date = fields.Date(
        string='Date de livraison',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', required=True)

    # Champs relationnels
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
    )

    order_id = fields.Many2one(
        'sale.order',
        related='dispatch_id.order_id',
        store=True,
        string='Commande'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
    )

    product_id = fields.Many2one(
        'product.product',
        related='dispatch_id.product_id',
        store=True,
        string='Produit'
    )

    # Relations Many2many
    move_ids = fields.Many2many(
        'stock.move',
        'sale_order_line_dispatch_delivery_move_rel',  # Renommé pour plus de clarté
        'delivery_id',
        'move_id',
        string='Mouvements de stock',
        copy=False
    )

    picking_ids = fields.Many2many(
        'stock.picking',
        'sale_order_line_dispatch_delivery_picking_rel',  # Ajout d'un nom explicite
        'delivery_id',
        'picking_id',
        string='Transferts',
        compute='_compute_picking_ids',
        store=True
    )

    notes = fields.Text(
        string='Notes',
        tracking=True
    )

    # Champs de base avec nouveaux types monétaires
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string="Devise"
    )

    # Nouveau système monétaire amélioré
    amount_untaxed = fields.Monetary(
        string='Montant HT',
        compute='_compute_amounts',
        store=True,
        tracking=True,
        currency_field='currency_id'
    )

    amount_tax = fields.Monetary(
        string='Taxes',
        compute='_compute_amounts',
        store=True,
        tracking=True,
        currency_field='currency_id'
    )

    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amounts',
        store=True,
        tracking=True,
        currency_field='currency_id'
    )

    # Relations optimisées
    shipping_address_id = fields.Many2one(
        'res.partner',
        required=True,
        tracking=True,
        index='btree',
        domain="[('id', 'in', allowed_shipping_address_ids)]"
    )

    # Champs de planification améliorés
    scheduled_date = fields.Datetime(
        required=True,
        tracking=True,
        index='btree',
        default=fields.Datetime.now
    )

    effective_date = fields.Datetime(
        tracking=True,
        readonly=True,
        copy=False
    )

    # Nouveaux champs de validation
    validation_user_id = fields.Many2one(
        'res.users',
        string='Validé par',
        tracking=True,
        readonly=True,
        copy=False
    )

    validation_date = fields.Datetime(
        string='Date de validation',
        tracking=True,
        readonly=True,
        copy=False
    )

    quantity = fields.Float(
        string='Quantité',
        required=True,
        default=0.0,
        digits='Product Unit of Measure',
        tracking=True
    )

    dispatched_qty = fields.Float(
        string='Quantité livrée',
        compute='_compute_dispatched_qty',
        store=True,
        digits='Product Unit of Measure'
    )

    allowed_shipping_address_ids = fields.Many2many(
        'res.partner',
        'sale_order_line_dispatch_delivery_address_rel',  # Ajout d'un nom explicite
        'delivery_id',
        'partner_id',
        string='Adresses de livraison autorisées',
        compute='_compute_allowed_shipping_address_ids',
        store=False
    )

    delivery_zone_id = fields.Many2one(
        'delivery.zone',
        string='Zone de livraison',
        required=True,
    )

    delivery_time_slot_id = fields.Many2one(
        'resource.calendar.attendance',
        string='Créneau horaire',
    )

    delivery_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Transporteur',
        required=True,
    )

    # Calculs
    @api.depends('move_ids.picking_id')
    def _compute_picking_ids(self):
        for record in self:
            record.picking_ids = record.move_ids.mapped('picking_id')

    @api.depends('dispatch_id')
    def _compute_allowed_shipping_address_ids(self):
        for record in self:
            if record.dispatch_id and record.dispatch_id.order_line_id:
                record.allowed_shipping_address_ids = record.dispatch_id.order_line_id.order_id.partner_id.child_ids
            else:
                record.allowed_shipping_address_ids = False

    @api.depends('quantity', 'state')
    def _compute_dispatched_qty(self):
        for record in self:
            record.dispatched_qty = record.quantity if record.state == 'done' else 0.0

    @api.depends('dispatch_id.quantity', 'dispatch_id.order_line_id.price_unit')
    def _compute_amounts(self):
        for delivery in self:
            amount_untaxed = delivery.dispatch_id.quantity * delivery.dispatch_id.order_line_id.price_unit
            taxes = delivery.dispatch_id.order_line_id.tax_id.compute_all(
                amount_untaxed,
                delivery.currency_id,
                1.0
            )
            delivery.amount_untaxed = taxes['total_excluded']
            delivery.amount_tax = taxes['total_included'] - taxes['total_excluded']
            delivery.amount_total = taxes['total_included']

    # Contraintes
    @api.constrains('delivered_qty')
    def _check_delivered_qty(self):
        for record in self:
            if float_compare(record.delivered_qty, 0.0, precision_rounding=0.01) < 0:
                raise ValidationError(_("La quantité livrée ne peut pas être négative"))

    @api.constrains('delivery_date')
    def _check_delivery_date(self):
        for record in self:
            if record.delivery_date and record.delivery_date < fields.Date.today():
                raise ValidationError(_("La date de livraison ne peut pas être dans le passé"))

    # Actions
    def action_plan(self):
        self.write({'state': 'planned'})

    def action_start_delivery(self):
        self.ensure_one()
        if self.state == 'planned':
            self.state = 'in_delivery'
        return True

    def action_validate(self):
        self._check_can_validate()
        self.write({'state': 'done'})
        self.dispatch_id._compute_delivered_qty()

    def action_cancel(self):
        self.ensure_one()
        if self.state not in ['done', 'cancel']:
            self.state = 'cancel'
        return True

    def action_reset(self):
        self._check_can_reset()
        self.write({'state': 'draft'})

    def action_confirm(self):
        for record in self:
            record.write({'state': 'confirmed'})

    def action_start(self):
        self.write({
            'state': 'in_progress',
            'effective_date': fields.Datetime.now()
        })

    # Méthodes de validation
    def _check_can_start_delivery(self):
        for record in self:
            if record.state != 'planned':
                raise UserError(_("La livraison doit être planifiée avant de commencer"))

    def _check_can_validate(self):
        for record in self:
            if record.state != 'in_delivery':
                raise UserError(_("La livraison doit être en cours avant d'être validée"))
            if float_compare(record.delivered_qty, 0.0, precision_rounding=0.01) <= 0:
                raise UserError(_("La quantité livrée doit être positive"))

    def _check_can_reset(self):
        for record in self:
            if record.state not in ['cancel', 'draft']:
                raise UserError(_("Seules les livraisons annulées ou en brouillon peuvent être réinitialisées"))

    def _validate_completion(self):
        self.ensure_one()
        if not self.effective_date:
            raise ValidationError(_("La date effective de livraison est requise"))

    def _check_cancellation(self):
        for delivery in self:
            if delivery.state == 'done':
                raise ValidationError(_("Impossible d'annuler une livraison terminée"))

    # Surcharges
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            dispatch = self.env['sale.order.line.dispatch'].browse(vals.get('dispatch_id'))
            if dispatch and dispatch.state not in ['draft', 'confirmed']:
                raise UserError(_("Impossible d'ajouter une livraison à un dispatch %s") % dispatch.state)
        return super().create(vals_list)

    # Méthodes utilitaires
    @api.model
    def _expand_states(self, states, domain, order):
        return [key for key, val in self._fields['state'].selection]

    # Champs mandant et mandataire maintenant correctement liés via dispatch_id
    mandant_id = fields.Many2one(
        'res.partner',
        related='dispatch_id.mandant_id',
        store=True,
        string='Société mandante'
    )

    mandataire_id = fields.Many2one(
        'res.partner',
        related='dispatch_id.mandataire_id',
        store=True,
        string='Mandataire'
    )

    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    def action_mark_done(self):
        self.ensure_one()
        if self.state == 'in_delivery':
            self.state = 'done'
        return True

    def action_set_to_draft(self):
        self.ensure_one()
        if self.state == 'cancel':
            self.state = 'draft'
        return True

    @api.onchange('delivery_zone_id')
    def _onchange_delivery_zone_id(self):
        if self.delivery_zone_id:
            return {'domain': {'delivery_carrier_id': [('id', 'in', self.delivery_zone_id.delivery_carrier_ids.ids)]}}
        return {'domain': {'delivery_carrier_id': []}}

    def action_done(self):
        for record in self:
            record.write({'state': 'done'})


