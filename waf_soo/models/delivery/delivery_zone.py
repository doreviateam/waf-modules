from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re
import random

class DeliveryZoneZipPrefix(models.Model):
    _name = 'delivery.zone.zip.prefix'
    _description = 'Préfixe de code postal pour zone de livraison'
    _order = 'zip_prefix'

    zone_id = fields.Many2one('delivery.zone', string='Zone', required=True, ondelete='cascade')
    zip_prefix = fields.Char(
        string='Préfixe code postal',
        size=3,
        required=True,
        help="Entrez les 2 ou 3 premiers chiffres du code postal"
    )

    _sql_constraints = [
        ('unique_prefix_per_zone', 'unique(zone_id, zip_prefix)', 
         'Ce préfixe existe déjà pour cette zone !')
    ]

    @api.constrains('zip_prefix')
    def _check_zip_prefix(self):
        for prefix in self:
            if not prefix.zip_prefix.isdigit():
                raise ValidationError(_("Le préfixe doit contenir uniquement des chiffres"))
            if len(prefix.zip_prefix) not in [2, 3]:
                raise ValidationError(_("Le préfixe doit contenir 2 ou 3 chiffres"))

class DeliveryZone(models.Model):
    """
    Gestion des zones de livraison avec support des nouvelles fonctionnalités Odoo 17.
    Permet de définir des zones géographiques pour la livraison avec des transporteurs associés.
    """
    _name = 'delivery.zone'
    _description = 'Zone de livraison'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    # Champs de base
    name = fields.Char(
        string='Nom',
        required=True,
        tracking=True,
        index='trigram',  # Optimisation des recherches textuelles
        copy=False,
        default=lambda self: _('Nouveau'),
        help="Nom unique de la zone de livraison"
    )
    
    sequence = fields.Integer(
        string='Séquence',
        default=10,
        index=True,
        help="Ordre d'affichage des zones"
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        tracking=True,
        index=True,
        help="Permet d'archiver/désarchiver la zone"
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Brouillon'),
            ('active', 'Active'),
            ('archived', 'Archivée')
        ],
        string='État',
        default='draft',
        tracking=True,
        required=True,
        index=True,
        group_expand='_expand_states',
        help="État actuel de la zone de livraison"
    )

    description = fields.Text(
        string='Description'
    )

    color = fields.Integer(
        string='Couleur',
        help="Permet une identification visuelle dans les vues kanban"
    )

    # Relations
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Société à laquelle appartient cette zone"
    )

    carrier_ids = fields.Many2many(
        'delivery.carrier',
        'delivery_zone_carrier_rel',
        'zone_id',
        'carrier_id',
        string='Transporteurs',
        domain="[]",
        tracking=True,
        help="Transporteurs autorisés pour cette zone"
    )

    country_id = fields.Many2one(
        'res.country',
        string='Pays',
        required=True,
        tracking=True,
        index=True,
        help="Pays de la zone de livraison"
    )

    state_ids = fields.Many2many(
        'res.country.state',
        'delivery_zone_state_rel',
        'zone_id',
        'state_id',
        string='États/Provinces',
        domain="[('country_id', '=', country_id)]",
        tracking=True,
        help="États ou provinces inclus dans la zone"
    )

    # Champs avancés
    pattern_type = fields.Selection([
        ('exact', 'Code postal exact'),
        ('start', 'Commence par'),
        ('multiple', 'Liste de codes postaux'),
        ('range', 'Plage de codes postaux'),
        ('custom', 'Pattern personnalisé'),
    ], string='Type de filtre', default='start', required=True)

    zip_pattern = fields.Char(string='Pattern Code Postal', compute='_compute_zip_pattern', store=True)
    zip_exact = fields.Char('Code postal exact')
    zip_start = fields.Char('Début du code postal')
    zip_list = fields.Text('Liste des codes postaux', help="Un code postal par ligne")
    zip_range_start = fields.Char('Code postal début')
    zip_range_end = fields.Char('Code postal fin')

    delivery_lead_time = fields.Float(
        string='Délai de livraison (jours)',
        default=1.0,
        tracking=True,
        help="Délai de livraison moyen pour cette zone"
    )

    delivery_instructions = fields.Html(
        string='Instructions de livraison',
        help="Instructions spécifiques pour les livraisons dans cette zone"
    )

    partner_ids = fields.Many2many(
        'res.partner',
        'delivery_zone_partner_rel',
        'zone_id',
        'partner_id',
        string='Clients de la zone',
        domain="[('type', '=', 'delivery')]",
        tracking=True,
        help="Clients associés à cette zone de livraison"
    )

    # Champs calculés
    partner_count = fields.Integer(
        string='Nombre de clients',
        compute='_compute_partner_count',
        store=True,
        help="Nombre total de clients dans la zone"
    )

    delivery_count = fields.Integer(
        string='Nombre de livraisons',
        compute='_compute_delivery_stats',
        store=True,
        help="Nombre total de livraisons dans la zone"
    )

    last_delivery_date = fields.Date(
        string='Dernière livraison',
        compute='_compute_delivery_stats',
        store=True,
        help="Date de la dernière livraison dans la zone"
    )

    zip_prefix_ids = fields.One2many(
        'delivery.zone.zip.prefix',
        'zone_id',
        string='Préfixes codes postaux',
        help="Liste des préfixes de codes postaux pour cette zone"
    )

    # Contraintes SQL
    _sql_constraints = [
        ('unique_name_company',
         'UNIQUE(name, company_id)',
         'Le nom de la zone doit être unique par société')
    ]

    # Méthodes de calcul
    @api.model
    def _expand_states(self, states, domain, order):
        """Permet l'expansion des états dans les vues kanban/recherche."""
        return [key for key, val in self._fields['state'].selection]

    @api.depends('partner_ids')
    def _compute_partner_count(self):
        """Calcule le nombre de clients dans la zone."""
        for zone in self:
            zone.partner_count = len(zone.partner_ids)

    @api.depends('partner_ids')
    def _compute_delivery_stats(self):
        """Calcule les statistiques de livraison pour la zone."""
        for zone in self:
            deliveries = self.env['stock.picking'].search([
                ('partner_id', 'in', zone.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'not in', ['draft', 'cancel'])
            ])
            zone.delivery_count = len(deliveries)
            if deliveries:
                zone.last_delivery_date = max(deliveries.mapped('date_done'))
            else:
                zone.last_delivery_date = False

    @api.depends('pattern_type', 'zip_exact', 'zip_start', 'zip_list', 'zip_range_start', 'zip_range_end')
    def _compute_zip_pattern(self):
        for zone in self:
            if zone.pattern_type == 'exact':
                zone.zip_pattern = f"^{zone.zip_exact}$"
            elif zone.pattern_type == 'start':
                zone.zip_pattern = f"^{zone.zip_start}.*"
            elif zone.pattern_type == 'multiple':
                codes = zone.zip_list.split('\n') if zone.zip_list else []
                zone.zip_pattern = f"^({'|'.join(codes)})$"
            elif zone.pattern_type == 'range':
                zone.zip_pattern = f"^({zone.zip_range_start}-{zone.zip_range_end})$"
            else:  # 'custom'
                zone.zip_pattern = zone.zip_pattern  # garde le pattern personnalisé

    # Contraintes
    @api.constrains('zip_pattern')
    def _check_zip_pattern(self):
        """Valide que le pattern de code postal est une expression régulière valide."""
        for zone in self:
            if zone.zip_pattern:
                try:
                    re.compile(zone.zip_pattern)
                except re.error:
                    raise ValidationError(_("Le pattern de code postal n'est pas une expression régulière valide"))

    @api.constrains('zip_prefix')
    def _check_zip_prefix(self):
        for zone in self:
            if not zone.zip_prefix.isdigit():
                raise ValidationError(_("Le préfixe doit contenir uniquement des chiffres"))
            if len(zone.zip_prefix) not in [2, 3]:
                raise ValidationError(_("Le préfixe doit contenir 2 ou 3 chiffres"))

    # Actions
    def action_activate(self):
        """Active la zone après validation des conditions requises."""
        self.ensure_one()
        if not self.carrier_ids:
            raise ValidationError(_("Vous devez assigner au moins un transporteur avant d'activer la zone"))
        self.write({'state': 'active'})

    def action_archive(self):
        """Archive la zone et la désactive."""
        self.write({'state': 'archived', 'active': False})

    def action_draft(self):
        """Remet la zone en brouillon."""
        self.write({'state': 'draft'})

    def action_view_partners(self):
        """Ouvre la vue des points de livraison de la zone."""
        self.ensure_one()
        return {
            'name': _('Points de livraison'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.partner_ids.ids)],
            'context': {'default_delivery_zone_ids': [(6, 0, [self.id])]}
        }

    def action_view_deliveries(self):
        """Ouvre la vue des livraisons pour cette zone."""
        self.ensure_one()
        return {
            'name': _('Livraisons'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', 'in', self.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing')
            ],
            'context': {'create': False}
        }

    # Méthodes utilitaires
    @api.model
    def _get_valid_zones_for_partner(self, partner):
        """
        Retourne les zones valides pour un partenaire donné.
        Utile pour la validation automatique des zones.
        """
        valid_zones = self.env['delivery.zone']
        if not partner or not partner.zip:
            return valid_zones

        zones = self.search([
            ('country_id', '=', partner.country_id.id),
            ('state_ids', 'in', partner.state_id.id if partner.state_id else False),
            ('state', '=', 'active')
        ])

        for zone in zones:
            if not zone.zip_pattern or re.match(zone.zip_pattern, partner.zip):
                valid_zones |= zone

        return valid_zones

    def name_get(self):
        """Personnalisation de l'affichage du nom des zones."""
        result = []
        for zone in self:
            name = f"{zone.name}"
            if zone.country_id:
                name = f"{name} ({zone.country_id.code})"
            result.append((zone.id, name))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'color' not in vals:
                vals['color'] = random.randint(1, 11)  # Odoo utilise généralement 11 couleurs
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('delivery.zone') or _('Nouveau')
        return super().create(vals_list)
    