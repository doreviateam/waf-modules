"""
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
import re
from dateutil.relativedelta import relativedelta
from odoo.tools import ormcache
from datetime import datetime, timedelta

class DeliveryZone(models.Model):
    _name = 'delivery.zone'
    _description = 'Zone de livraison'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    # Optimisation des champs de base avec index
    name = fields.Char(
        string='Nom',
        required=True,
        tracking=True,
        index='trigram',  # Améliore la recherche par similarité
        help="Nom de la zone de livraison"
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        index='btree_not_null',  # Index optimisé pour les recherches exactes
        help="Code unique de la zone de livraison"
    )
    
    sequence = fields.Integer(
        string='Séquence',
        default=10,
        help="Ordre d'affichage"
    )
    
    active = fields.Boolean(
        default=True,
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Active'),
        ('archived', 'Archivée')
    ], 
        string='État',
        default='draft',
        tracking=True,
        required=True,
        copy=False
    )

    # Champs de configuration
    is_multi_carrier = fields.Boolean(
        string='Multi-transporteurs',
        default=False,
        tracking=True,
        help="Permet d'utiliser plusieurs transporteurs dans cette zone"
    )

    delivery_lead_time = fields.Integer(
        string='Délai de livraison (jours)',
        default=1,
        tracking=True,
        help="Délai moyen de livraison dans cette zone"
    )

    min_amount = fields.Monetary(
        string='Montant minimum',
        currency_field='currency_id',
        tracking=True,
        help="Montant minimum de commande pour cette zone"
    )

    # Nouveaux champs pour la gestion des capacités
    max_daily_deliveries = fields.Integer(
        string='Capacité journalière max',
        required=True,
        default=50,
        tracking=True
    )

    available_capacity = fields.Integer(
        string='Capacité disponible',
        compute='_compute_available_capacity',
        store=True,
        help="Nombre de livraisons encore possibles aujourd'hui"
    )

    delivery_count = fields.Integer(
        string='Nombre de livraisons',
        compute='_compute_delivery_stats',
        store=True
    )

    utilization_rate = fields.Float(
        string="Taux d'utilisation",
        compute='_compute_delivery_stats',
        store=True,
        help="Pourcentage d'utilisation de la capacité"
    )

    # Relations
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        groups="base.group_multi_company",
    )

    currency_id = fields.Many2one(related='company_id.currency_id')

    partner_ids = fields.Many2many(
        'res.partner',
        string='Partenaires',
        domain="[('is_company', '=', True)]",
        tracking=True,
    )

    delivery_carrier_ids = fields.Many2many(
        'delivery.carrier',
        string='Transporteurs',
        tracking=True,
    )

    default_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Transporteur par défaut',
        tracking=True,
    )

    adjacent_zone_ids = fields.Many2many(
        'delivery.zone',
        relation='delivery_zone_adjacent_rel',
        column1='zone_id',
        column2='adjacent_zone_id',
        string='Zones adjacentes',
        help="Zones de livraison adjacentes pour optimisation des tournées"
    )

    # Champs calculés
    partner_count = fields.Integer(
        string='Nombre de partenaires',
        compute='_compute_partner_count',
    )

    delivery_order_count = fields.Integer(
        string='Nombre de livraisons',
        compute='_compute_delivery_order_count',
    )

    # Contraintes de livraison
    delivery_days = fields.Many2many(
        'resource.calendar.attendance',
        string='Jours de livraison',
        tracking=True,
    )

    delivery_time_slots = fields.Many2many(
        'resource.calendar.attendance',
        string='Créneaux horaires',
        relation='zone_time_slots_rel',
        tracking=True,
    )

    # Statistiques optimisées
    delivery_success_rate = fields.Float(
        string='Taux de succès des livraisons',
        compute='_compute_delivery_stats',
        store=True,
        group_operator='avg',
        help="Pourcentage de livraisons réussies"
    )

    on_time_delivery_rate = fields.Float(
        string='Taux de livraisons à l\'heure',
        compute='_compute_delivery_stats',
        store=True,
        group_operator='avg',
        help="Pourcentage de livraisons effectuées dans les délais"
    )

    notes = fields.Text(
        string='Notes',
        help='Notes et commentaires sur la zone de livraison',
        tracking=True,
    )

    # Calculs
    @api.depends('partner_ids')
    def _compute_partner_count(self):
        for zone in self:
            zone.partner_count = len(zone.partner_ids)

    @api.depends('partner_ids.delivery_ids', 'max_daily_deliveries')
    def _compute_available_capacity(self):
        today = fields.Date.today()
        for zone in self:
            domain = [
                ('partner_id', 'in', zone.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('scheduled_date', '>=', today),
                ('scheduled_date', '<', today + timedelta(days=1)),
                ('state', 'not in', ['cancel', 'draft'])
            ]
            scheduled_count = self.env['stock.picking'].search_count(domain)
            zone.available_capacity = max(0, zone.max_daily_deliveries - scheduled_count)

    @api.depends('partner_ids.delivery_ids')
    def _compute_delivery_stats(self):
        for zone in self:
            deliveries = self.env['stock.picking'].search([
                ('partner_id', 'in', zone.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'not in', ['cancel', 'draft'])
            ])
            
            zone.delivery_count = len(deliveries)
            
            if zone.max_daily_deliveries:
                zone.utilization_rate = (zone.delivery_count / zone.max_daily_deliveries) * 100
            else:
                zone.utilization_rate = 0.0

    def _compute_delivery_order_count(self):
        for zone in self:
            zone.delivery_order_count = self.env['sale.order'].search_count([
                ('delivery_zone_id', '=', zone.id),
                ('state', 'not in', ['draft', 'cancel']),
            ])

    # Contraintes et validations
    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if not re.match("^[a-zA-Z0-9]+$", record.code):
                raise ValidationError(_("Le code ne doit contenir que des caractères alphanumériques."))

    @api.constrains('default_carrier_id', 'delivery_carrier_ids')
    def _check_default_carrier(self):
        for zone in self:
            if zone.default_carrier_id and zone.default_carrier_id not in zone.delivery_carrier_ids:
                raise ValidationError(_("Le transporteur par défaut doit faire partie des transporteurs autorisés."))

    # Actions
    def action_activate(self):
        for record in self:
            record.state = 'active'

    def action_archive(self):
        for record in self:
            record.state = 'archived'

    def action_view_partners(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Clients',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.partner_ids.ids)],
        }

    def action_view_deliveries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Livraisons',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('delivery_zone_id', '=', self.id)],
        }

    # Méthodes CRUD optimisées
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('delivery.zone')
        return super().create(vals_list)

    def write(self, vals):
        if 'code' in vals:
            self._check_code_modification()
        return super().write(vals)

    def _check_code_modification(self):
        for zone in self:
            if zone.partner_ids and zone.state != 'draft':
                raise ValidationError(_("Impossible de modifier le code d'une zone active contenant des clients."))

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update({
            'name': _('%s (copie)') % self.name,
            'code': False,
            'partner_ids': [],
            'state': 'draft',
        })
        return super().copy(default)

    # Méthodes de recherche
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        args = args or []
        domain = []
        
        if name:
            domain = [('name', operator, name)]
            
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)

    # Contraintes SQL optimisées
    _sql_constraints = [
        ('unique_code_company',
         'UNIQUE(code, company_id)',
         'Le code doit être unique par société'),
        ('check_delivery_lead_time',
         'CHECK(delivery_lead_time > 0)',
         'Le délai de livraison doit être positif')
    ]

    # Méthode de validation améliorée
    def action_validate_capacity(self):
        """Vérifie la capacité disponible pour les livraisons planifiées"""
        self.ensure_one()
        if not self.max_daily_deliveries:
            return True

        if self.available_capacity <= 0:
            raise ValidationError(_(
                "La zone %(zone)s a atteint sa capacité maximale de %(max)d livraisons par jour",
                zone=self.name,
                max=self.max_daily_deliveries
            ))
        return True

    # Cache optimisé pour les partenaires actifs
    @api.model
    @ormcache('zone_id', 'company_id')
    def _get_active_partners(self, zone_id, company_id):
        """Retourne les partenaires actifs d'une zone"""
        zone = self.browse(zone_id)
        return zone.with_company(company_id).partner_ids.filtered('active').ids

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            return {'domain': {'delivery_carrier_ids': ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)]}}
        return {'domain': {'delivery_carrier_ids': []}}


