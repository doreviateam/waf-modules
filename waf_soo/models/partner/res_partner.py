from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class Contact(models.Model):
    _inherit = 'res.partner'
    _description = 'Contact with Delivery Addresses'

    # Optimisation des champs avec index et préchargement
    address_ids = fields.Many2many(
        'partner.address',
        'partner_address_rel',
        column1='partner_id',
        column2='address_id',
        string='Liste des adresses de livraison',
        copy=False,
        tracking=True,
        index=True,
        prefetch=True,  # Optimisation Odoo 17
    )

    delivery_address_count = fields.Integer(
        string="Nombre d'adresses de livraison",
        compute='_compute_delivery_address_count',
        store=True,
        index=True,
        help="Nombre total d'adresses de livraison associées",
    )

    # Ajout de champs pour optimiser les recherches
    has_delivery_address = fields.Boolean(
        string="A des adresses de livraison",
        compute='_compute_has_delivery_address',
        store=True,
        index=True,  # Ajout d'index pour optimiser les recherches
        help="Indique si le contact possède au moins une adresse de livraison",
    )

    default_delivery_address_id = fields.Many2one(
        'partner.address',
        string='Adresse de livraison par défaut',
        compute='_compute_default_delivery_address',
        store=True,
        index=True,
        help="Adresse de livraison par défaut pour ce contact",
    )

    @api.depends('address_ids')
    def _compute_has_delivery_address(self):
        """Calcule si le contact a des adresses de livraison."""
        for record in self.filtered(lambda r: r.id):  # Optimisation pour éviter les enregistrements non sauvegardés
            record.has_delivery_address = bool(record.address_ids)

    @api.depends('address_ids', 'address_ids.type')
    def _compute_delivery_address_count(self):
        """Calcule le nombre d'adresses de livraison en utilisant read_group pour optimisation."""
        if not self.ids:
            return

        # Optimisation avec read_group et préchargement
        self.env['partner.address'].flush_model(['partner_ids', 'type'])
        grouped_data = self.env['partner.address'].with_context(active_test=False).read_group(
            [('partner_ids', 'in', self.ids), ('type', '=', 'delivery')],
            fields=['partner_ids'],
            groupby=['partner_ids'],
            lazy=False
        )
        
        counts = {group['partner_ids'][0]: group['__count'] for group in grouped_data if group['partner_ids']}
        
        for record in self:
            record.delivery_address_count = counts.get(record.id, 0)

    @api.depends('address_ids', 'address_ids.type')
    def _compute_default_delivery_address(self):
        """Calcule l'adresse de livraison par défaut."""
        for record in self:
            default_address = record.address_ids.filtered(
                lambda a: a.type == 'delivery' and a.active
            )[:1]
            record.default_delivery_address_id = default_address

    def _prepare_delivery_address_values(self):
        """Prépare les valeurs pour la création d'une adresse de livraison avec validation."""
        self.ensure_one()
        required_fields = ['street', 'city', 'zip', 'country_id']
        
        # Vérification optimisée des champs requis
        missing_fields = [
            field for field in required_fields 
            if not self[field] and field in self._fields
        ]
        
        if missing_fields:
            raise ValidationError(_(
                "Les champs suivants sont requis pour créer une adresse de livraison: %s"
            ) % ', '.join(missing_fields))

        return {
            'name': self.name,
            'street': self.street,
            'street2': self.street2 or False,
            'city': self.city,
            'zip': self.zip,
            'state_id': self.state_id.id if self.state_id else False,
            'country_id': self.country_id.id,
            'type': 'delivery',
            'active': True,
        }

    @api.model_create_multi
    @api.returns('self', lambda value: value.id)
    def create(self, vals_list):
        """Création optimisée avec gestion en batch des adresses."""
        # Optimisation avec prefetch et création en batch
        partners = super().create(vals_list)
        
        # Préparation des adresses en batch
        delivery_addresses_to_create = []
        partners_to_update = self.env['res.partner']
        
        for partner in partners.filtered('is_company'):
            if all(partner[field] for field in ['street', 'city', 'zip', 'country_id']):
                delivery_addresses_to_create.append(partner._prepare_delivery_address_values())
                partners_to_update |= partner

        # Création en batch des adresses
        if delivery_addresses_to_create:
            addresses = self.env['partner.address'].create(delivery_addresses_to_create)
            # Mise à jour en batch des relations
            for partner, address in zip(partners_to_update, addresses):
                partner.address_ids = [(4, address.id)]

        return partners

    def action_view_delivery_addresses(self):
        """Action pour afficher les adresses de livraison."""
        self.ensure_one()
        
        # Optimisation du contexte
        ctx = {
            'default_partner_ids': [(4, self.id)],
            'default_name': self.name,
            'default_type': 'delivery',
            'search_default_active': 1,
        }
        
        return {
            'name': _('Adresses de livraison'),
            'type': 'ir.actions.act_window',
            'res_model': 'partner.address',
            'view_mode': 'tree,form',
            'domain': [('partner_ids', 'in', self.id), ('type', '=', 'delivery')],
            'context': ctx,
            'target': 'current',
        }
