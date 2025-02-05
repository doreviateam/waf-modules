from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Champs techniques
    available_delivery_partners = fields.Many2many(
        'res.partner',
        compute='_compute_available_delivery_partners',
        store=True,
        help="Partenaires disponibles pour la livraison"
    )

    # Relations
    agent_id = fields.Many2one(
        'res.partner',
        string="Mandant",
        tracking=True,
        domain="[('is_agent', '=', True)]",
        index=True,
        help="Agent responsable de la commande"
    )

    groupment_ids = fields.Many2many(
        'partner.groupment',
        string="Groupements",
        tracking=True,
        domain="[('agent_id', '=', agent_id), ('state', '=', 'active')]",
        help="Groupements concernés par la commande"
    )

    delivery_partner_ids = fields.Many2many(
        'res.partner',
        'sale_order_delivery_rel',
        'order_id',
        'partner_id',
        string='Points de livraison',
        tracking=True,
        domain="[('id', 'in', available_delivery_partners)]",
        help="Partenaires destinataires de la commande"
    )

    # Méthodes calculées
    @api.depends('groupment_ids')
    def _compute_available_delivery_partners(self):
        """Calcule la liste des partenaires disponibles pour la livraison"""
        for order in self:
            order.available_delivery_partners = order.groupment_ids.mapped('member_ids')

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
        """Réinitialise les champs liés lors du changement d'agent"""
        self.groupment_ids = False
        self.delivery_partner_ids = False

    @api.onchange('groupment_ids')
    def _onchange_groupment_ids(self):
        """Met à jour les destinataires lors du changement de groupements"""
        self.delivery_partner_ids = False

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