"""
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from odoo.tools import ormcache

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'
    _description = 'Extension Partenaire pour Odoo 17'

    is_groupment_member = fields.Boolean(
        string='Membre de groupement',
        default=False,
        tracking=True
    )

    is_mandataire = fields.Boolean(
        string='Est mandataire',
        default=False,
        tracking=True
    )

    # Relations Many2many
    delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        'res_partner_delivery_zone_rel',
        'partner_id',
        'zone_id',
        string='Zones de livraison'
    )

    groupment_ids = fields.Many2many(
        'partner.groupment',
        'res_partner_groupment_rel',
        'partner_id',
        'groupment_id',
        string='Groupements'
    )

    delivery_weekday_ids = fields.Many2many(
        'delivery.weekday',
        'res_partner_delivery_weekday_rel',
        'partner_id',
        'weekday_id',
        string='Jours de livraison'
    )

    delivery_time_slot_ids = fields.Many2many(
        'delivery.time.slot',
        'res_partner_delivery_time_slot_rel',
        'partner_id',
        'time_slot_id',
        string='Créneaux de livraison'
    )

    interest_ids = fields.Many2many(
        'partner.interest',
        'res_partner_interest_rel',
        'partner_id',
        'interest_id',
        string="Centres d'intérêt"
    )

    interest_category_ids = fields.Many2many(
        'partner.interest.category',
        string='Catégories d\'intérêt',
    )

    # Champs avec nouveaux types et décorateurs
    partner_type = fields.Selection([
        ('customer', 'Client'),
        ('mandataire', 'Mandataire'),
        ('member', 'Membre'),
    ], string='Type de partenaire',
       tracking=True,
       help="Définit le rôle du partenaire dans le système")

    # Relations optimisées
    managed_groupment_ids = fields.One2many(
        'partner.groupment',
        'mandataire_id',
        string='Groupements gérés',
        help="Groupements dont ce partenaire est responsable"
    )

    member_groupment_ids = fields.Many2many(
        'partner.groupment',
        'partner_groupment_member_rel',
        'partner_id',
        'groupment_id',
        string='Appartient aux groupements',
        domain="[('state', '=', 'active')]",
        copy=False
    )

    # Statistiques
    dispatch_count = fields.Integer(
        string='Nombre de dispatches',
        compute='_compute_dispatch_stats',
        help="Nombre total de dispatches associés"
    )

    dispatch_amount = fields.Monetary(
        string='Montant dispatché',
        compute='_compute_dispatch_stats',
        help="Montant total des dispatches"
    )

    is_default_contact = fields.Boolean(
        string='Contact par défaut',
        help="Indique si ce contact est le mandataire par défaut de la société"
    )

    # Utilisation de compute_sudo pour les champs calculés qui ne dépendent pas des droits d'accès
    groupment_count = fields.Integer(
        string='Nombre de groupements',
        compute='_compute_groupment_stats',
        compute_sudo=True,
        help="Nombre total de groupements associés"
    )

    # Nouveau décorateur depends_context pour la performance
    @api.depends_context('company', 'active_test')
    @api.depends('member_groupment_ids', 'managed_groupment_ids', 'partner_type')
    def _compute_groupment_stats(self):
        for partner in self:
            if partner.partner_type == 'mandataire':
                partner.groupment_count = len(partner.with_context(active_test=False).managed_groupment_ids)
            else:
                partner.groupment_count = len(partner.with_context(active_test=False).member_groupment_ids)

    @api.depends('groupment_ids')
    def _compute_dispatch_stats(self):
        for partner in self:
            # Recherche des dispatches liés aux groupements du partenaire
            dispatches = self.env['sale.order.line.dispatch'].search([
                ('groupment_id', 'in', partner.groupment_ids.ids),
                ('state', '=', 'done')
            ])
            partner.dispatch_count = len(dispatches)
            partner.dispatch_amount = sum(d.amount_total for d in dispatches)

    # Contraintes avec nouveaux décorateurs
    @api.constrains('partner_type', 'groupment_ids')
    def _check_member_type(self):
        for partner in self:
            if partner.groupment_ids and partner.partner_type not in ['member', 'mandataire']:
                raise ValidationError(_(
                    "Seuls les membres et les mandataires peuvent être associés à des groupements"
                ))

    @api.constrains('partner_type', 'managed_groupment_ids')
    def _check_manager_type(self):
        for partner in self:
            if partner.managed_groupment_ids and partner.partner_type != 'mandataire':
                raise ValidationError(_(
                    "Seuls les mandataires peuvent être responsables de groupements"
                ))

    # Utilisation de constrains_domain pour les contraintes simples
    _sql_constraints = [
        ('default_contact_unique', 
         'CHECK(NOT (is_default_contact AND type != \'contact\'))',
         'Seul un contact peut être marqué comme contact par défaut.')
    ]

    # Nouveau style pour les contraintes Python
    @api.constrains('is_default_contact', 'parent_id', 'type')
    def _check_default_contact(self):
        for partner in self:
            if not partner.is_default_contact or not partner.parent_id:
                continue
            other_default = self.search([
                ('id', '!=', partner.id),
                ('parent_id', '=', partner.parent_id.id),
                ('is_default_contact', '=', True),
                ('type', '=', 'contact')
            ], limit=1)
            if other_default:
                raise ValidationError(_(
                    "Il ne peut y avoir qu'un seul contact par défaut par société.\n"
                    "%(contact)s est déjà le contact par défaut pour %(company)s",
                    contact=other_default.name,
                    company=partner.parent_id.name
                ))

    # Utilisation de nouveaux décorateurs pour les actions
    @api.model
    def action_view_groupments(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('waf_preso.action_partner_groupment')
        
        if self.partner_type == 'mandataire':
            action['domain'] = [('id', 'in', self.managed_groupment_ids.ids)]
            action['context'] = {'default_mandataire_id': self.id}
        else:
            action['domain'] = [('id', 'in', self.member_groupment_ids.ids)]
            action['context'] = {'default_member_ids': [(4, self.id)]}
        
        return action

    def action_view_dispatches(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dispatches'),
            'res_model': 'sale.order.line.dispatch',
            'view_mode': 'tree,form',
            'domain': [
                ('groupment_id', 'in', self.groupment_ids.ids),
                ('state', '=', 'done')
            ],
            'context': {'create': False}
        }

    # Garder ormcache au lieu de @api.cache
    @api.model
    @ormcache('partner_id', 'company_id')
    def _get_partner_groupments(self, partner_id, company_id):
        partner = self.browse(partner_id)
        return partner.with_company(company_id).member_groupment_ids.ids

    def _address_fields(self):
        """Retourne une liste vide pour les sociétés pour empêcher la synchronisation"""
        if self.is_company:
            return []
        return super()._address_fields()

    @api.model_create_multi
    def create(self, vals_list):
        partners = []
        for vals in vals_list:
            partner = super().create([vals])[0]
            partners.append(partner.id)
        return self.browse(partners)

    def write(self, vals):
        return super().write(vals)

    @api.onchange('parent_id')
    def onchange_parent_id(self):
        if self.is_company:
            return {'value': {}}
        return super().onchange_parent_id()

    def _get_name(self):
        name = super()._get_name()
        if self._context.get('show_type') and self.partner_type:
            name = f"{name} ({dict(self._fields['partner_type'].selection).get(self.partner_type, '')})"
        return name

    # Relations
    delivery_zone_id = fields.Many2one('delivery.zone', string='Zone de livraison', 
                                      tracking=True)

    # Préférences de livraison
    preferred_delivery_time = fields.Char(string='Horaire préféré', 
                                        help="Exemple: Matin, Après-midi...")
    requires_appointment = fields.Boolean('Rendez-vous requis', default=False)
    delivery_instructions = fields.Text('Instructions de livraison')

    # Compteurs pour les statistiques
    delivery_count = fields.Integer(
        string='Nombre de livraisons',
        compute='_compute_delivery_stats',
        store=True
    )

    on_time_delivery_rate = fields.Float(
        string="Taux de livraison à temps",
        compute='_compute_delivery_stats',
        store=True,
        help="Pourcentage de livraisons effectuées dans les délais"
    )

    # Relations
    delivery_day_ids = fields.Many2many(
        'delivery.weekday',
        'res_partner_delivery_weekday_rel',  # Nom de table explicite
        'partner_id',
        'weekday_id',
        string='Jours de livraison possibles'
    )
    
    # Contraintes
    min_delivery_amount = fields.Monetary('Montant minimum de livraison', 
                                        currency_field='currency_id')

    # Statistiques
    average_delivery_time = fields.Float('Temps moyen de livraison', compute='_compute_delivery_stats')
    last_delivery_date = fields.Datetime('Dernière livraison', compute='_compute_delivery_stats')

    delivery_ids = fields.One2many(
        'stock.picking',
        'partner_id',
        string='Livraisons',
        domain=[('picking_type_code', '=', 'outgoing')],
        help="Livraisons associées à ce partenaire"
    )

    @api.depends('delivery_ids.state', 'delivery_ids.date_done', 'delivery_ids.scheduled_date')
    def _compute_delivery_stats(self):
        for partner in self:
            partner.delivery_count = len(partner.delivery_ids)
            
            completed_deliveries = partner.delivery_ids.filtered(lambda d: d.state == 'done')
            total_completed = len(completed_deliveries)
            
            if not total_completed:
                partner.on_time_delivery_rate = 0.0
                continue

            on_time = len(completed_deliveries.filtered(
                lambda d: d.date_done and d.scheduled_date and
                d.date_done <= d.scheduled_date
            ))
            
            partner.on_time_delivery_rate = (on_time / total_completed) * 100

    def action_view_deliveries(self):
        self.ensure_one()
        return {
            'name': _('Livraisons'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.delivery_ids.ids)],
            'context': {'create': False}
        }

    
