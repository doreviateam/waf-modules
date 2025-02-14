"""
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class PartnerInterest(models.Model):
    _name = 'partner.interest'
    _description = "Centre d'intérêt partenaire"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id desc'
    _translate = True  

    # Champs de base
    name = fields.Char(
        string="Nom",
        required=True,
        translate=True,
        tracking=True,
        index='trigram',  
        help="Nom du centre d'intérêt"
    )

    sequence = fields.Integer(
        default=10,
        index='btree'  
    )

    currency_id = fields.Many2one(
        'res.currency', 
        string='Devise',
        related='company_id.currency_id',
        store=True,
        readonly=True
    )

    code = fields.Char(
        string="Code",
        required=True,
        tracking=True,
        index='btree_not_null',  
        copy=False
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
        index='btree'
    )

    # Champs descriptifs avec support multilingue amélioré
    description = fields.Html(
        string="Description",
        translate=True,
        tracking=True,
        sanitize=True,
        sanitize_tags=True,
        sanitize_attributes=True
    )

    # Relations avec index optimisés
    category_id = fields.Many2one(
        'partner.interest.category',
        string="Catégorie",
        required=True,
        tracking=True,
        index='btree',
        ondelete='restrict'
    )

    groupment_ids = fields.One2many(
        'partner.groupment',
        'interest_id',
        string="Groupements associés",
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index='btree'
    )

    # Relations Many2many
    mandant_ids = fields.Many2many(
        'res.partner',
        'partner_interest_mandant_rel',
        'interest_id',
        'partner_id',
        string='Mandants',
        compute='_compute_mandants',
        store=True,
        help="Liste des mandants des groupements"
    )

    partner_ids = fields.Many2many(
        'res.partner',
        'partner_interest_partner_rel',
        'interest_id',
        'partner_id',
        string="Partenaires associés",
        compute='_compute_partner_ids',
        store=True,
        compute_sudo=True,
        tracking=True,
        auto_join=True
    )

    # Champs statistiques avec calcul optimisé
    partner_count = fields.Integer(
        string="Nombre de partenaires",
        compute='_compute_stats',
        store=True
    )

    groupment_count = fields.Integer(
        string="Nombre de groupements",
        compute='_compute_groupment_stats',
        store=True
    )

    total_partners = fields.Integer(
        string="Nombre total de partenaires",
        compute='_compute_groupment_stats',
        store=True
    )

    notification_partner_ids = fields.Many2many(
        'res.partner',
        'partner_interest_notification_rel',
        'interest_id',
        'partner_id',
        string="Destinataires additionnels",
        help="Partenaires à notifier en plus des responsables de groupements",
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('archived', 'Archivé')
    ], string='État', default='active', required=True, tracking=True)

    # Nouveaux champs de catégorisation
    tag_ids = fields.Many2many(
        'partner.interest.tag',
        string="Tags",
        tracking=True
    )

    priority = fields.Selection([
        ('0', 'Faible'),
        ('1', 'Normal'),
        ('2', 'Élevé'),
        ('3', 'Très élevé')
    ], default='1', tracking=True)

    # Statistiques améliorées
    activity_level = fields.Selection([
        ('inactive', 'Inactif'),
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé')
    ], compute='_compute_activity_level', store=True)

    revenue_contribution = fields.Monetary(
        string="Contribution au CA",
        compute='_compute_revenue_stats',
        store=True,
        currency_field='currency_id'
    )

    growth_rate = fields.Float(
        string="Taux de croissance",
        compute='_compute_revenue_stats',
        store=True,
        help="Taux de croissance sur les 12 derniers mois"
    )

    def _get_notification_recipients(self):
        """Détermine les destinataires des notifications"""
        self.ensure_one()
        recipients = self.env['res.partner']
        
        # Responsables des groupements
        for groupment in self.groupment_ids:
            if groupment.manager_id:
                recipients |= groupment.manager_id.partner_id
        
        # Destinataires additionnels
        recipients |= self.notification_partner_ids
        
        return recipients.filtered(lambda p: p.email)

    def _notify_changes(self, changes):
        """Gère l'envoi des notifications lors des changements"""
        self.ensure_one()
        recipients = self._get_notification_recipients()
        if not recipients:
            return

        # Mapping des templates selon le type de changement
        notification_mapping = {
            'groupment_ids': {
                'template': 'partner_interest.mail_template_groupment_changed',
                'subject': _('Modification des groupements pour %s', self.name)
            },
            'state': {
                'template': 'partner_interest.mail_template_state_changed',
                'subject': _('Changement d\'état pour %s', self.name)
            }
        }

        for field, change in changes.items():
            if field in notification_mapping:
                template = self.env.ref(
                    notification_mapping[field]['template'],
                    raise_if_not_found=False
                )
                if template:
                    template.with_context(
                        changed_field=field,
                        old_value=change[0],
                        new_value=change[1]
                    ).send_mail(
                        self.id,
                        force_send=True,
                        email_values={
                            'recipient_ids': [(6, 0, recipients.ids)],
                            'subject': notification_mapping[field]['subject']
                        }
                    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge pour notifier à la création"""
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('partner.interest')
        records = super().create(vals_list)
        for record in records:
            recipients = record._get_notification_recipients()
            if recipients:
                template = self.env.ref('partner_interest.mail_template_interest_created')
                if template:
                    template.send_mail(record.id, force_send=True)
        return records

    def write(self, vals):
        """Surcharge de la méthode write pour gérer le tracking"""
        # Désactiver temporairement le tracking mail
        self = self.with_context(tracking_disable=True)
        
        # Appel du write parent
        res = super(PartnerInterest, self).write(vals)
        
        # Réactiver le tracking pour les prochaines opérations
        self = self.with_context(tracking_disable=False)
        
        return res

    @api.depends('groupment_ids', 'groupment_ids.partner_ids')
    def _compute_partner_ids(self):
        """Calcule automatiquement les partenaires associés à ce centre d'intérêt"""
        for record in self:
            partners = self.env['res.partner']
            for groupment in record.groupment_ids:
                partners |= groupment.partner_ids
            record.partner_ids = partners

    def action_view_partners(self):
        """Affiche les partenaires liés à ce centre d'intérêt"""
        self.ensure_one()
        return {
            'name': _('Partenaires'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', self.partner_ids.ids)],
            'context': {
                'default_interest_ids': [(4, self.id)],
                'search_default_customer': 1
            }
        }

    # Calculs avec mise en cache optimisée
    @api.depends('partner_ids', 'groupment_ids')
    def _compute_stats(self):
        for record in self:
            record.partner_count = len(record.with_context(active_test=False).partner_ids)
            record.groupment_count = len(record.with_context(active_test=False).groupment_ids)

    # Contraintes SQL optimisées
    _sql_constraints = [
        ('unique_code_company',
         'UNIQUE(code, company_id)',
         'Le code doit être unique par société!')
    ]

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        args = args or []
        domain = []
        if name:
            domain = ['|',
                ('name', operator, name),
                ('code', operator, name)
            ]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid, order=order)

    @api.depends('groupment_ids', 'groupment_ids.mandant_id')
    def _compute_mandants(self):
        for record in self:
            record.mandant_ids = record.groupment_ids.mapped('mandant_id')

    @api.depends('groupment_ids', 'groupment_ids.partner_ids')
    def _compute_groupment_stats(self):
        for record in self:
            record.groupment_count = len(record.groupment_ids)
            all_partners = record.groupment_ids.mapped('partner_ids')
            record.total_partners = len(all_partners)

    @api.depends('groupment_ids.partner_ids.sale_order_ids')
    def _compute_activity_level(self):
        today = fields.Date.today()
        three_months_ago = today - relativedelta(months=3)
        
        for interest in self:
            domain = [
                ('partner_id', 'in', interest.groupment_ids.mapped('partner_ids').ids),
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', three_months_ago)
            ]
            order_count = self.env['sale.order'].search_count(domain)
            
            if order_count == 0:
                interest.activity_level = 'inactive'
            elif order_count < 10:
                interest.activity_level = 'low'
            elif order_count < 50:
                interest.activity_level = 'medium'
            else:
                interest.activity_level = 'high'

    @api.depends('groupment_ids.partner_ids.sale_order_ids.amount_total',
                'groupment_ids.partner_ids.sale_order_ids.state',
                'groupment_ids.partner_ids.sale_order_ids.date_order')
    def _compute_revenue_stats(self):
        today = fields.Date.today()
        last_year = today - relativedelta(years=1)
        
        for interest in self:
            # Calcul du CA actuel
            current_revenue = self._get_period_revenue(interest, last_year, today)
            interest.revenue_contribution = current_revenue
            
            # Calcul du CA précédent pour le taux de croissance
            previous_start = last_year - relativedelta(years=1)
            previous_revenue = self._get_period_revenue(interest, previous_start, last_year)
            
            if previous_revenue:
                interest.growth_rate = ((current_revenue - previous_revenue) / previous_revenue) * 100
            else:
                interest.growth_rate = 0.0

    def _get_period_revenue(self, interest, start_date, end_date):
        domain = [
            ('partner_id', 'in', interest.groupment_ids.mapped('partner_ids').ids),
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', start_date),
            ('date_order', '<', end_date)
        ]
        orders = self.env['sale.order'].search(domain)
        
        total = 0.0
        for order in orders:
            total += order.currency_id._convert(
                order.amount_total,
                interest.company_id.currency_id,
                interest.company_id,
                order.date_order or fields.Date.today()
            )
        return total

    def action_generate_report(self):
        """Génère un rapport d'analyse du centre d'intérêt"""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'waf_preso.report_partner_interest_analysis',
            'report_type': 'qweb-pdf',
            'data': {
                'interest_id': self.id,
                'date_from': fields.Date.to_string(fields.Date.today() - relativedelta(months=12)),
                'date_to': fields.Date.to_string(fields.Date.today()),
            }
        }

    def notify_activity_change(self):
        """Notifie les responsables des changements d'activité"""
        template = self.env.ref('waf_preso.mail_template_interest_activity_change', raise_if_not_found=False)
        if not template:
            return

        for interest in self:
            if interest.activity_level in ['inactive', 'low']:
                template.send_mail(
                    interest.id,
                    force_send=True,
                    email_values={'subject': f"Alerte activité : {interest.name}"}
                )


