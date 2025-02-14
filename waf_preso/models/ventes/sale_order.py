from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Relations Many2many
    groupment_ids = fields.Many2many(
        'partner.groupment',
        'sale_order_groupment_rel',  # Simplifié
        'order_id',
        'groupment_id',
        string='Groupements',
    )

    # les stackholders sont des partenaires sélectionnés dans les groupements
    stakeholder_ids = fields.Many2many(
        'res.partner',
        'sale_order_stakeholder_rel',
        'order_id',
        'partner_id',
        string='Parties Prenantes',
        domain="[('id', 'in', available_partner_ids)]",
        context={'show_address': 1},
        check_company=True,
        index=True,
        copy=False,
        tracking=True,
        ondelete='restrict',
        help="""Partenaires sélectionnés appartenant aux groupements.
        Ces parties prenantes sont impliquées dans la commande groupée
        et peuvent recevoir des dispatches.""",
    )

    is_groupment_order = fields.Boolean(
        string='Commande groupée',
        compute='_compute_is_groupment_order',
        store=True,
        index=True,
    )

    # Champs mandataire
    mandant_id = fields.Many2one(
        'res.partner',
        string='Société mandante',
        domain="[('is_company', '=', True), ('is_mandataire', '=', True)]",
        tracking=True,
        index=True,
        check_company=True,
    )

    mandataire_id = fields.Many2one(
        'res.partner',
        string='Mandataire',
        domain="[('parent_id', '=', mandant_id), ('type', '=', 'contact')]",
        tracking=True,
        index=True,
    )

    # Relations Many2many
    delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        'sale_order_delivery_zone_rel',  # Déjà bien nommé
        'order_id',
        'zone_id',
        string='Zones de livraison',
        tracking=True,
        domain="[('state', '=', 'active'), ('id', 'in', available_delivery_zone_ids)]",
        check_company=True,
    )

    available_delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        'sale_order_available_zone_rel',  # Ajout d'un nom explicite
        'order_id',
        'zone_id',
        compute='_compute_available_delivery_zones',
        store=True,
        help="Zones de livraison disponibles basées sur les groupements"
    )

    multi_zone_delivery = fields.Boolean(
        string='Livraison multi-zones',
        compute='_compute_multi_zone_delivery',
        store=True,
        help="Indique si la commande nécessite une livraison sur plusieurs zones"
    )

    delivery_zone_partner_ids = fields.Many2many(
        'res.partner',
        'sale_order_zone_partner_rel',  # Ajout d'un nom explicite
        'order_id',
        'partner_id',
        compute='_compute_delivery_zone_partner_ids',
        store=True,
        help="Partenaires disponibles dans les zones de livraison sélectionnées"
    )

    # Statistiques
    dispatch_count = fields.Integer(
        string='Nombre de dispatches',
        compute='_compute_dispatch_stats',
        store=True,
    )

    dispatched_amount = fields.Monetary(
        string='Montant dispatché',
        compute='_compute_dispatch_stats',
        store=True,
    )

    dispatch_completion_rate = fields.Float(
        string='Taux de dispatch',
        compute='_compute_dispatch_stats',
        store=True,
        group_operator='avg',
    )

    dispatch_state = fields.Selection([
        ('not_required', 'Non requis'),
        ('to_dispatch', 'À dispatcher'),
        ('partial', 'Partiellement dispatché'),
        ('dispatched', 'Dispatché'),
        ('cancelled', 'Dispatch annulé')
    ], string='État du dispatch',
       compute='_compute_dispatch_state',
       store=True,
       index=True,
    )

    mandataire_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Liste de prix mandataire',
        compute='_compute_mandataire_pricelist',
        store=True,
        readonly=False,
        domain="[('id', 'in', available_mandataire_pricelist_ids)]",
    )

    available_mandataire_pricelist_ids = fields.Many2many(
        'product.pricelist',
        'sale_order_mandataire_pricelist_rel',  # Déjà bien nommé
        'order_id',
        'pricelist_id',
        compute='_compute_available_mandataire_pricelists',
    )

    available_partner_ids = fields.Many2many(
        'res.partner',
        'sale_order_available_partner_rel',  # Déjà bien nommé
        'order_id',
        'partner_id',
        compute='_compute_available_partner_ids',
    )

    dispatch_ids = fields.One2many(
        'sale.order.line.dispatch', 
        'order_id', 
        string='Dispatches'
    )

    delivery_zone_id = fields.Many2one(
        'delivery.zone',
        string='Zone de livraison',
        tracking=True,
    )

    delivery_weekday_id = fields.Many2one(
        'delivery.weekday',
        string='Jour de livraison',
        tracking=True,
        domain="[('id', 'in', available_delivery_weekday_ids)]",
    )

    available_delivery_weekday_ids = fields.Many2many(
        'delivery.weekday',
        compute='_compute_available_delivery_weekday_ids',
        string='Jours de livraison disponibles',
    )

    delivery_time_slot_id = fields.Many2one(
        'delivery.time.slot',
        string='Créneau de livraison',
        tracking=True,
        domain="[('id', 'in', available_delivery_time_slot_ids)]",
    )

    available_delivery_time_slot_ids = fields.Many2many(
        'delivery.time.slot',
        compute='_compute_available_delivery_time_slot_ids',
        string='Créneaux de livraison disponibles',
    )

    dispatch_line_ids = fields.One2many(
        'sale.order.line.dispatch',
        'order_id',
        string='Lignes de répartition',
    )

    groupment_id = fields.Many2one(
        'partner.groupment',
        string='Groupement',
        compute='_compute_groupment',
        store=True,
    )

    interest_ids = fields.Many2many(
        comodel_name='partner.interest',
        relation='sale_order_interest_rel',
        column1='order_id',
        column2='interest_id',
        string='Centres d\'intérêt',
        related='partner_id.interest_ids',
        store=True,
    )

    @api.depends('groupment_ids')
    def _compute_available_partner_ids(self):
        for order in self:
            order.available_partner_ids = order.groupment_ids.mapped('partner_ids')

    @api.depends('groupment_ids', 'groupment_ids.delivery_zone_ids')
    def _compute_available_delivery_zones(self):
        for order in self:
            order.available_delivery_zone_ids = order.groupment_ids.mapped('delivery_zone_ids')

    @api.depends('delivery_zone_ids')
    def _compute_multi_zone_delivery(self):
        for order in self:
            order.multi_zone_delivery = len(order.delivery_zone_ids) > 1

    @api.depends('delivery_zone_ids', 'delivery_zone_ids.partner_ids')
    def _compute_delivery_zone_partner_ids(self):
        for order in self:
            order.delivery_zone_partner_ids = order.delivery_zone_ids.mapped('partner_ids')

    @api.depends('groupment_ids')
    def _compute_is_groupment_order(self):
        for order in self:
            order.is_groupment_order = bool(order.groupment_ids)

    @api.depends('order_line.dispatch_ids', 'order_line.dispatch_ids.state')
    def _compute_dispatch_stats(self):
        self.env.cr.execute("""
            SELECT sol.order_id,
                   COUNT(DISTINCT d.id) as dispatch_count,
                   COALESCE(SUM(CASE WHEN d.state = 'done' 
                       THEN d.quantity * sol.price_unit ELSE 0 END), 0) as amount
            FROM sale_order_line sol
            LEFT JOIN sale_order_line_dispatch d ON d.order_line_id = sol.id
            WHERE sol.order_id IN %s
            GROUP BY sol.order_id
        """, (tuple(self.ids),))
        
        results = {r[0]: {'count': r[1], 'amount': r[2]} 
                  for r in self.env.cr.fetchall()}
        
        for order in self:
            stats = results.get(order.id, {'count': 0, 'amount': 0.0})
            order.dispatch_count = stats['count']
            order.dispatched_amount = stats['amount']
            order.dispatch_completion_rate = (
                (stats['amount'] / order.amount_total * 100)
                if order.amount_total else 0.0
            )

    @api.depends('order_line.dispatch_ids.state', 'is_groupment_order')
    def _compute_dispatch_state(self):
        for order in self:
            if not order.is_groupment_order:
                order.dispatch_state = 'not_required'
                continue

            dispatches = order.mapped('order_line.dispatch_ids')
            if not dispatches:
                order.dispatch_state = 'to_dispatch'
            elif all(d.state == 'cancel' for d in dispatches):
                order.dispatch_state = 'cancelled'
            elif all(d.state == 'done' for d in dispatches):
                order.dispatch_state = 'dispatched'
            else:
                order.dispatch_state = 'partial'

    @api.constrains('partner_shipping_id', 'delivery_zone_ids')
    def _check_delivery_zones(self):
        for order in self:
            if order.delivery_zone_ids and order.partner_shipping_id:
                if not any(order.partner_shipping_id in zone.partner_ids 
                          for zone in order.delivery_zone_ids):
                    raise ValidationError(_(
                        "L'adresse de livraison doit appartenir à au moins "
                        "une des zones de livraison sélectionnées"
                    ))

    @api.constrains('groupment_ids', 'delivery_zone_ids')
    def _check_delivery_zones_groupments(self):
        for order in self:
            if order.is_groupment_order:
                allowed_zones = order.groupment_ids.mapped('delivery_zone_ids')
                if not all(zone in allowed_zones for zone in order.delivery_zone_ids):
                    raise ValidationError(_(
                        "Les zones de livraison sélectionnées doivent être "
                        "autorisées pour les groupements de la commande"
                    ))

    def action_confirm(self):
        for order in self:
            if order.is_groupment_order and not order.delivery_zone_ids:
                raise UserError(_("Au moins une zone de livraison est requise pour les commandes groupées"))
            
            # Vérification des montants minimums par zone
            for zone in order.delivery_zone_ids:
                if zone.min_amount > 0:
                    zone_partners = order.order_line.mapped('dispatch_ids').filtered(
                        lambda d: d.partner_id in zone.partner_ids
                    ).mapped('partner_id')
                    for partner in zone_partners:
                        amount = sum(d.amount for d in order.order_line.mapped('dispatch_ids').filtered(
                            lambda d: d.partner_id == partner
                        ))
                        if amount < zone.min_amount:
                            raise UserError(_(
                                "Le montant minimum de commande (%s) n'est pas atteint "
                                "pour le partenaire %s dans la zone %s"
                            ) % (zone.min_amount, partner.name, zone.name))
                            
        return super().action_confirm()

    def action_create_dispatch(self):
        self.ensure_one()
        if not self.is_groupment_order:
            raise UserError(_("Seules les commandes groupées peuvent être dispatchées"))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Créer Dispatch'),
            'res_model': 'create.delivery.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_groupment_ids': [(6, 0, self.groupment_ids.ids)],
                'default_delivery_zone_ids': [(6, 0, self.delivery_zone_ids.ids)],
            }
        }

    def _prepare_delivery_line_vals(self, carrier, delivery_price):
        vals = super()._prepare_delivery_line_vals(carrier, delivery_price)
        if self.multi_zone_delivery:
            # Ajustement du prix pour les livraisons multi-zones
            zone_count = len(self.delivery_zone_ids)
            vals['price_unit'] = delivery_price * (1 + 0.1 * (zone_count - 1))
        return vals

    @api.depends('dispatch_ids')
    def _compute_dispatch_count(self):
        for order in self:
            order.dispatch_count = len(order.dispatch_ids)

    def action_view_dispatch_deliveries(self):
        self.ensure_one()
        action = self.env.ref('waf_preso.action_sale_order_line_dispatch').read()[0]
        action['domain'] = [('order_id', '=', self.id)]
        action['context'] = {'default_order_id': self.id}
        return action

    @api.depends('delivery_zone_id')
    def _compute_available_delivery_weekday_ids(self):
        for order in self:
            if order.delivery_zone_id:
                order.available_delivery_weekday_ids = order.delivery_zone_id.weekday_ids
            else:
                order.available_delivery_weekday_ids = False

    @api.depends('delivery_zone_id', 'delivery_weekday_id')
    def _compute_available_delivery_time_slot_ids(self):
        for order in self:
            if order.delivery_zone_id and order.delivery_weekday_id:
                order.available_delivery_time_slot_ids = order.delivery_weekday_id.time_slot_ids.filtered(
                    lambda slot: slot in order.delivery_zone_id.time_slot_ids
                )
            else:
                order.available_delivery_time_slot_ids = False

    @api.depends('partner_id', 'partner_id.groupment_ids')
    def _compute_groupment(self):
        for order in self:
            order.groupment_id = order.partner_id.groupment_ids[:1].id if order.partner_id.groupment_ids else False