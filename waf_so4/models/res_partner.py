from odoo import fields, models, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    address_ids = fields.Many2many(
        'partner.address',
        'partner_address_rel',
        column1='partner_id',
        column2='address_id',
        string='Delivery Addresses'
    )

    default_shipping_address_id = fields.Many2one(
        'partner.address',
        string='Adresse de livraison par défaut',
        domain="[('id', 'in', address_ids)]",
        tracking=True,
        help="Adresse de livraison utilisée par défaut pour ce partenaire"
    )

    dispatch_line_ids = fields.One2many(
        'sale.line.dispatch',
        'stakeholder_id',
        string='Dispatch Lines',
        help="Dispatch lines where this partner is stakeholder"
    )

    order_ids = fields.Many2many(
        'sale.order',
        'sale_order_stakeholder_rel',
        'partner_id',
        'order_id',
        string='Commandes concernées',
        help="Commandes en mode dispatch où ce partenaire est concerné",
        domain=[('delivery_mode', '=', 'dispatch')]
    )

    order_count = fields.Integer(
        string='Nombre de commandes',
        compute='_compute_order_count',
        help="Nombre de commandes en mode dispatch où ce partenaire est concerné"
    )

    hide_main_company = fields.Boolean(
        string="Hide Main Company Info on Documents",
        default=False
    )
    hide_company_on = fields.Selection([
        ('all', 'All Documents'),
        ('delivery', 'Delivery Documents Only'),
        ('invoice', 'Invoices Only'),
    ], string="Hide Company Info On", 
    default='all',
    help="Select on which type of documents the main company information should be hidden")

    @api.onchange('address_ids')
    def _onchange_address_ids(self):
        """Reset default address if not in available addresses"""
        if self.default_shipping_address_id and self.default_shipping_address_id not in self.address_ids:
            self.default_shipping_address_id = False

    @api.model_create_multi
    def create(self, vals_list):
        """Create partners and their associated delivery addresses"""
        partners = super().create(vals_list)
        
        for partner in partners:
            # Ne créer l'adresse que pour les partenaires principaux avec une adresse
            if not partner.parent_id and (partner.street or partner.city or partner.zip):
                # Création de l'adresse de livraison basée sur l'adresse du partenaire
                partner_address = self.env['partner.address'].create({
                    'name': partner.name,
                    'street': partner.street or '',
                    'street2': partner.street2 or '',
                    'city': partner.city or '',
                    'zip': partner.zip or '',
                    'state_id': partner.state_id.id if partner.state_id else False,
                    'country_id': partner.country_id.id if partner.country_id else False,
                    'phone': partner.phone or '',
                    'email': partner.email or '',
                    'type': 'delivery',
                    'partner_ids': [(4, partner.id)],
                })
                
                # Définir comme adresse par défaut
                partner.default_shipping_address_id = partner_address.id

        return partners

    def write(self, vals):
        """Mettre à jour l'adresse de livraison par défaut si l'adresse principale change"""
        res = super().write(vals)
        
        # Vérifier si des champs d'adresse ont été modifiés
        address_fields = ['street', 'street2', 'city', 'zip', 'state_id', 'country_id']
        if any(field in vals for field in address_fields):
            for partner in self:
                if partner.default_shipping_address_id:
                    # Mise à jour de l'adresse de livraison par défaut
                    partner.default_shipping_address_id.write({
                        'street': partner.street or '',
                        'street2': partner.street2 or '',
                        'city': partner.city or '',
                        'zip': partner.zip or '',
                        'state_id': partner.state_id.id if partner.state_id else False,
                        'country_id': partner.country_id.id if partner.country_id else False,
                    })
        return res 

    @api.depends('order_ids')
    def _compute_order_count(self):
        for partner in self:
            partner.order_count = len(partner.order_ids)

    def action_view_orders(self):
        """Ouvre la vue des commandes concernées"""
        self.ensure_one()
        action = {
            'name': 'Commandes concernées',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.order_ids.ids)],
            'context': {'default_delivery_mode': 'dispatch', 'default_stakeholder_ids': [(4, self.id)]},
        }
        if len(self.order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.order_ids.id,
            })
        return action 