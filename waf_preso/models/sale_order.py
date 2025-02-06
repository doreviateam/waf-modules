from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Champs techniques
    available_delivery_partners = fields.Many2many(
        'res.partner',
        'sale_order_available_partner_rel',
        'order_id',
        'partner_id',
        string='Points de livraison disponibles'
    )

    dispatch_line_ids = fields.One2many(
        comodel_name='sale.order.line.dispatch',
        inverse_name='order_id',
        string='Lignes de dispatching',
        help="Lignes de dispatching"
    )

    # Relations
    agent_id = fields.Many2one(
        'res.partner',
        string='Mandant',
        domain=[('is_agent', '=', True)],
        tracking=True
    )

    groupment_id = fields.Many2one(
        'partner.groupment',
        string='Groupement principal',
        tracking=True
    )

    groupment_ids = fields.Many2many(
        'partner.groupment',
        string='Groupements',
        tracking=True
    )

    delivery_partner_ids = fields.Many2many(
        'res.partner',
        string='Points de livraison',
        tracking=True
    )

    allowed_delivery_partner_ids = fields.Many2many(
        'res.partner',
        'sale_order_allowed_delivery_rel',
        'order_id',
        'partner_id',
        compute='_compute_allowed_delivery_partner_ids',
        store=True,
        string='Points de livraison autorisés'
    )

    delivery_planning_ids = fields.One2many(
        'sale.order.line.dispatch.delivery',
        'order_id',
        string='Livraisons planifiées',
    )

    # Méthodes calculées
    @api.depends('groupment_id', 'groupment_ids', 'groupment_ids.member_ids')
    def _compute_delivery_partner_ids(self):
        for order in self:
            # Sélectionner les partenaires qui sont membres des groupements sélectionnés
            order.delivery_partner_ids = order.groupment_ids.mapped('member_ids')

    @api.depends('dispatch_line_ids.delivery_ids')
    def _compute_delivery_planning_ids(self):
        for order in self:
            deliveries = self.env['sale.order.line.dispatch.delivery'].search([
                ('dispatch_id', 'in', order.dispatch_line_ids.ids)
            ])
            order.delivery_planning_ids = deliveries

    @api.depends('groupment_ids', 'groupment_ids.member_ids')
    def _compute_allowed_delivery_partner_ids(self):
        for order in self:
            if order.groupment_ids:
                order.allowed_delivery_partner_ids = order.groupment_ids.mapped('member_ids')
            else:
                order.allowed_delivery_partner_ids = self.env['res.partner']

    # Contraintes
    @api.constrains('groupment_ids', 'delivery_partner_ids')
    def _check_delivery_partners(self):
        """Vérifie la cohérence des partenaires de livraison"""
        for order in self:
            if order.groupment_ids and not order.delivery_partner_ids:
                raise ValidationError(_("Vous devez sélectionner au moins un destinataire pour les groupements choisis."))
            
            invalid_partners = order.delivery_partner_ids - order.groupment_ids.mapped('member_ids')
            if invalid_partners:
                raise ValidationError(_(
                    "Les partenaires suivants ne sont pas membres des groupements sélectionnés : %s"
                ) % ', '.join(invalid_partners.mapped('name')))

    # Onchange
    @api.onchange('agent_id')
    def _onchange_agent_id(self):
        """Vide les groupements si l'agent change"""
        self.groupment_ids = False
        return {'domain': {'groupment_ids': [
            ('agent_id', '=', self.agent_id.id),
            ('state', '=', 'active')
        ]}}

    @api.onchange('groupment_id')
    def _onchange_groupment_id(self):
        if self.groupment_id:
            self.groupment_ids = [(4, self.groupment_id.id, 0)]

    # Surcharges
    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la création pour validation supplémentaire"""
        for vals in vals_list:
            if vals.get('groupment_ids') and not vals.get('delivery_partner_ids'):
                raise ValidationError(_("Vous devez sélectionner au moins un destinataire."))
        return super().create(vals_list)

    def write(self, vals):
        """Surcharge de l'écriture pour validation supplémentaire"""
        res = super().write(vals)
        if 'groupment_ids' in vals or 'delivery_partner_ids' in vals:
            self._check_delivery_partners()
        return res

    def action_confirm(self):
        """Surcharge de la confirmation pour validation supplémentaire"""
        for order in self:
            if order.groupment_ids and not order.delivery_partner_ids:
                raise UserError(_("Vous devez sélectionner au moins un destinataire avant de confirmer la commande."))
        return super().action_confirm()

    def get_delivery_partners_ids(self):
        self.ensure_one()
        return self.delivery_partner_ids.ids