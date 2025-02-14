"""
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import image_process
import re
from datetime import datetime

class PartnerGroupment(models.Model):
    _name = 'partner.groupment'
    _description = 'Groupement de partenaires'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _check_company_auto = True

    # Champs de base optimisés
    name = fields.Char(
        string='Nom',
        required=True,
        tracking=True,
        index='trigram',
        translate=True
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        index='btree_not_null'
    )
    
    sequence = fields.Integer(
        default=10
    )
    
    active = fields.Boolean(
        default=True,
        tracking=True
    )

    note = fields.Html(
        string='Notes',
        help="Notes et commentaires sur ce groupement"
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('archived', 'Archivé')
    ], string='État',
        default='draft',
        required=True,
        tracking=True
    )

    # Champs de livraison
    delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        string='Zones de livraison',
        tracking=True
    )

    default_delivery_zone_id = fields.Many2one(
        'delivery.zone',
        string='Zone de livraison par défaut',
        tracking=True,
        domain="[('id', 'in', delivery_zone_ids)]"
    )

    delivery_carrier_ids = fields.Many2many(
        'delivery.carrier',
        'partner_groupment_carrier_rel',
        'groupment_id',
        'carrier_id',
        string='Transporteurs autorisés',
        tracking=True
    )

    # Images optimisées
    image = fields.Image(
        string="Logo",
        max_width=1920,
        max_height=1920,
        verify_resolution=True,
    )
    
    image_medium = fields.Image(
        "Image moyenne", 
        related="image",
        max_width=128,
        max_height=128,
        store=True
    )
    
    image_small = fields.Image(
        "Image miniature", 
        related="image",
        max_width=64,
        max_height=64,
        store=True
    )

    # Relations principales
    mandant_id = fields.Many2one(
        'res.partner',
        string='Mandant',
        required=True,
        tracking=True,
        domain="[('is_company', '=', True)]",
        help="Société responsable du groupement"
    )

    mandataire_id = fields.Many2one(
        'res.partner',
        string='Mandataire',
        tracking=True,
        domain="[('type', '=', 'contact'), ('parent_id', '=', mandant_id)]",
        help="Contact principal du groupement"
    )

    partner_ids = fields.Many2many(
        'res.partner',
        string='Membres',
        tracking=True,
        domain="[('is_company', '=', True)]"
    )

    # Champs de configuration
    property_payment_term_id = fields.Many2one(
        'account.payment.term',
        company_dependent=True,
        string='Conditions de paiement',
        tracking=True
    )
    
    property_delivery_carrier_id = fields.Many2one(
        'delivery.carrier',
        company_dependent=True,
        string='Méthode de livraison préférée',
        tracking=True,
        domain="[('id', 'in', delivery_carrier_ids)]"
    )

    min_order_amount = fields.Monetary(
        string='Montant minimum de commande',
        currency_field='company_currency_id',
        tracking=True
    )

    delivery_instructions = fields.Text(
        string='Instructions de livraison',
        translate=True,
        tracking=True
    )

    # Champs administratifs
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        groups="base.group_multi_company",
        tracking=True
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string="Devise de la société"
    )

    interest_id = fields.Many2one(
        'partner.interest',
        string="Centre d'intérêt",
        required=True,
        tracking=True,
        ondelete='restrict'
    )

    category_ids = fields.Many2many(
        'res.partner.category',
        'partner_groupment_category_rel',
        'groupment_id',
        'category_id',
        string='Catégories',
        tracking=True
    )

    # Nouveaux champs de gestion
    manager_ids = fields.Many2many(
        'res.users',
        'partner_groupment_manager_rel',
        'groupment_id',
        'user_id',
        string='Gestionnaires',
        tracking=True,
        help="Utilisateurs autorisés à gérer ce groupement"
    )

    active_member_count = fields.Integer(
        string='Membres actifs',
        compute='_compute_member_stats',
        store=True
    )

    last_activity_date = fields.Datetime(
        string='Dernière activité',
        compute='_compute_activity_stats',
        store=True
    )

    activity_level = fields.Selection([
        ('inactive', 'Inactif'),
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé')
    ], string='Niveau d\'activité',
        compute='_compute_activity_stats',
        store=True
    )

    delivery_count = fields.Integer(
        string='Nombre de livraisons',
        compute='_compute_activity_stats',
        store=True
    )

    # Statistiques financières
    total_revenue = fields.Monetary(
        string='Chiffre d\'affaires total',
        compute='_compute_financial_stats',
        store=True,
        currency_field='company_currency_id'
    )

    average_order_value = fields.Monetary(
        string='Panier moyen',
        compute='_compute_financial_stats',
        store=True,
        currency_field='company_currency_id'
    )

    # Dates
    date_start = fields.Date(
        string='Date de début',
        required=True,
        default=fields.Date.today,
        tracking=True
    )

    date_end = fields.Date(
        string='Date de fin',
        tracking=True
    )

    # Calculs
    @api.depends('partner_ids')
    def _compute_partner_count(self):
        for record in self:
            record.partner_count = len(record.partner_ids)

    @api.depends('partner_ids.sale_order_ids.amount_total', 
                'partner_ids.sale_order_ids.state',
                'partner_ids.sale_order_ids.currency_id')
    def _compute_total_sales(self):
        for groupment in self:
            total = 0.0
            for partner in groupment.partner_ids:
                confirmed_sales = partner.sale_order_ids.filtered(
                    lambda s: s.state in ('sale', 'done')
                )
                for sale in confirmed_sales:
                    total += sale.currency_id._convert(
                        sale.amount_total,
                        groupment.company_currency_id,
                        groupment.company_id,
                        sale.date_order or fields.Date.today()
                    )
            groupment.total_sales = total

    @api.depends('partner_ids.sale_order_ids.state')
    def _compute_delivery_stats(self):
        for groupment in self:
            pickings = self.env['stock.picking'].search([
                ('partner_id', 'in', groupment.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'in', ['done', 'cancel'])
            ])
            
            total_pickings = len(pickings)
            if total_pickings:
                successful_pickings = len(pickings.filtered(lambda p: p.state == 'done'))
                groupment.delivery_success_rate = (successful_pickings / total_pickings) * 100
            else:
                groupment.delivery_success_rate = 0.0

    @api.depends('partner_ids.active')
    def _compute_member_stats(self):
        for groupment in self:
            groupment.active_member_count = len(groupment.partner_ids.filtered('active'))

    @api.depends('partner_ids.delivery_ids.state', 'partner_ids.delivery_ids.date_done')
    def _compute_activity_stats(self):
        for groupment in self:
            deliveries = self.env['stock.picking'].search([
                ('partner_id', 'in', groupment.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'not in', ['cancel', 'draft'])
            ], order='date_done DESC')

            groupment.delivery_count = len(deliveries)
            
            if deliveries:
                groupment.last_activity_date = deliveries[0].date_done
                
                # Calcul du niveau d'activité basé sur le nombre de livraisons
                if groupment.delivery_count > 100:
                    groupment.activity_level = 'high'
                elif groupment.delivery_count > 50:
                    groupment.activity_level = 'medium'
                elif groupment.delivery_count > 0:
                    groupment.activity_level = 'low'
                else:
                    groupment.activity_level = 'inactive'
            else:
                groupment.last_activity_date = False
                groupment.activity_level = 'inactive'

    @api.depends('partner_ids.sale_order_ids.amount_total',
                'partner_ids.sale_order_ids.state',
                'partner_ids.sale_order_ids.date_order')
    def _compute_financial_stats(self):
        def convert_amount(amount, from_currency, to_currency, company, date):
            if from_currency == to_currency:
                return amount
            return from_currency._convert(amount, to_currency, company, date)

        for groupment in self:
            total_amount = 0.0
            order_count = 0
            
            for partner in groupment.partner_ids:
                orders = partner.sale_order_ids.filtered(
                    lambda o: o.state in ('sale', 'done')
                )
                
                for order in orders:
                    amount = convert_amount(
                        order.amount_total,
                        order.currency_id,
                        groupment.company_currency_id,
                        groupment.company_id,
                        order.date_order or fields.Date.today()
                    )
                    total_amount += amount
                    order_count += 1

            groupment.total_revenue = total_amount
            groupment.average_order_value = total_amount / order_count if order_count else 0

    # Contraintes
    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if not re.match("^[a-zA-Z0-9-]+$", record.code):
                raise ValidationError(_("Le code ne doit contenir que des caractères alphanumériques et des tirets."))

    @api.constrains('mandant_id', 'mandataire_id')
    def _check_mandataire_belongs_to_mandant(self):
        for record in self:
            if record.mandataire_id and record.mandataire_id.parent_id != record.mandant_id:
                raise ValidationError(_("Le mandataire doit être un contact du mandant sélectionné"))

    @api.constrains('default_delivery_zone_id', 'delivery_zone_ids')
    def _check_default_delivery_zone(self):
        for record in self:
            if record.default_delivery_zone_id and record.default_delivery_zone_id not in record.delivery_zone_ids:
                raise ValidationError(_("La zone de livraison par défaut doit faire partie des zones autorisées"))

    @api.constrains('partner_ids', 'delivery_zone_ids')
    def _check_partners_zones(self):
        for groupment in self:
            if groupment.delivery_zone_ids:  # Vérifie seulement si des zones sont définies
                invalid_partners = groupment.partner_ids.filtered(
                    lambda p: p.delivery_zone_ids and not any(
                        zone in groupment.delivery_zone_ids for zone in p.delivery_zone_ids
                    )
                )
                if invalid_partners:
                    raise ValidationError(_(
                        "Les partenaires suivants ont des zones de livraison qui ne sont pas autorisées dans le groupement :\n%s",
                        '\n'.join(invalid_partners.mapped('name'))
                    ))

    @api.constrains('company_id', 'delivery_zone_ids')
    def _check_delivery_zones_company(self):
        """Vérifie la cohérence des sociétés pour les zones de livraison"""
        for record in self:
            if any(zone.company_id and zone.company_id != record.company_id 
                  for zone in record.delivery_zone_ids):
                raise ValidationError(_(
                    "Les zones de livraison doivent appartenir à la même société "
                    "que le groupement ou être sans société."
                ))

    @api.constrains('company_id', 'partner_ids')
    def _check_partners_company(self):
        """Vérifie la cohérence des sociétés pour les partenaires"""
        for record in self:
            if any(partner.company_id and partner.company_id != record.company_id 
                  for partner in record.partner_ids):
                raise ValidationError(_(
                    "Les partenaires doivent appartenir à la même société "
                    "que le groupement ou être sans société."
                ))

    # Actions
    def action_view_partners(self):
        self.ensure_one()
        return {
            'name': _('Membres'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', self.partner_ids.ids)],
            'context': {'default_groupment_id': self.id},
        }

    def action_view_deliveries(self):
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

    def action_send_summary(self):
        """Envoie un résumé d'activité aux gestionnaires"""
        self.ensure_one()
        template = self.env.ref('waf_preso.mail_template_groupment_summary', raise_if_not_found=False)
        if not template:
            return False

        context = {
            'active_member_count': self.active_member_count,
            'total_revenue': self.total_revenue,
            'average_order_value': self.average_order_value,
            'last_activity_date': self.last_activity_date
        }

        template.with_context(**context).send_mail(
            self.id,
            force_send=True,
            email_values={'recipient_ids': [(6, 0, self.manager_ids.mapped('partner_id').ids)]}
        )
        return True

    def action_activate(self):
        """Activer le groupement"""
        self.ensure_one()
        if self.state == 'draft':
            self.write({
                'state': 'active',
                'active': True
            })

    def action_archive(self):
        """Archiver le groupement"""
        self.ensure_one()
        if self.state == 'active':
            self.write({
                'state': 'archived',
                'active': False
            })

    def write(self, vals):
        """Surcharge de write pour gérer l'archivage"""
        if 'active' in vals and not vals.get('active'):
            vals['state'] = 'archived'
        elif 'active' in vals and vals.get('active') and self.filtered(lambda g: g.state == 'archived'):
            vals['state'] = 'active'
        if vals.get('image'):
            vals['image'] = image_process(vals['image'])
        if 'company_id' in vals:
            for record in self:
                record._check_company_id(vals)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de create pour gérer l'état initial"""
        for vals in vals_list:
            if 'state' not in vals:
                vals['state'] = 'draft'
            if 'active' not in vals:
                vals['active'] = vals.get('state') == 'active'
            if vals.get('image'):
                vals['image'] = image_process(vals['image'])
            if 'company_id' in vals:
                self._check_company_id(vals)
        return super().create(vals_list)

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update({
            'name': _('%s (copie)') % self.name,
            'partner_ids': [],
            'code': False,
            'state': 'draft',
        })
        return super().copy(default)

    @api.onchange('mandant_id')
    def _onchange_mandant_id(self):
        self.mandataire_id = False
        if self.mandant_id:
            default_contact = self.env['res.partner'].search([
                ('parent_id', '=', self.mandant_id.id),
                ('type', '=', 'contact'),
                ('is_default_contact', '=', True)
            ], limit=1)
            
            if default_contact:
                self.mandataire_id = default_contact
            
            if not self.image and self.mandant_id.image_1920:
                self.image = self.mandant_id.image_1920

    def _check_company_id(self, vals):
        """Vérifie la cohérence de la société pour les enregistrements liés"""
        if vals.get('company_id'):
            company_id = vals['company_id']
            # Vérifier les zones de livraison
            if self.delivery_zone_ids:
                zones = self.delivery_zone_ids.filtered(
                    lambda z: z.company_id and z.company_id.id != company_id
                )
                if zones:
                    raise ValidationError(_(
                        "Vous ne pouvez pas changer la société car certaines zones "
                        "de livraison appartiennent à une autre société."
                    ))

    @api.model
    def _get_default_company_id(self):
        return self.env.company.id

    @api.model
    def default_get(self, fields_list):
        """Surcharge pour définir les valeurs par défaut"""
        res = super().default_get(fields_list)
        if 'company_id' in fields_list:
            res['company_id'] = self._get_default_company_id()
        return res


