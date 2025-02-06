from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class PartnerGroupment(models.Model):
    _name = 'partner.groupment'
    _description = 'Groupement de partenaires'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    
    # Champs techniques
    sequence = fields.Integer(string='Séquence', default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', 
        string='Société',
        default=lambda self: self.env.company,
        index=True
    )
    
    # Champs principaux
    name = fields.Char(
        string='Nom',
        required=True,
        tracking=True,
        index=True,
        translate=True
    )
    code = fields.Char(
        string='Code',
        tracking=True,
        copy=False,
        index=True
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
    ], string='État', default='draft', tracking=True, index=True)
    
    # Relations
    parent_id = fields.Many2one(
        'partner.groupment',
        string='Groupement parent',
        tracking=True
    )
    member_ids = fields.Many2many(
        'res.partner',
        string='Liste des adhérents',
        domain="[('id', 'in', allowed_member_ids)]"
    )
    agent_id = fields.Many2one(
        'res.partner',
        string='Agent',
        required=True,
        tracking=True,
        domain="[('is_company', '=', True), ('is_agent', '=', True)]",
        index=True
    )
    interest_id = fields.Many2one(
        'partner.interest',
        string='Centre d\'intérêt principal',
        tracking=True,
        index=True
    )
    
    # Champs calculés
    member_count = fields.Integer(
        string='Nombre de membres',
        compute='_compute_member_count',
        store=True
    )
    allowed_member_ids = fields.Many2many(
        'res.partner',
        'partner_groupment_allowed_members_rel',
        'groupment_id',
        'partner_id',
        compute='_compute_allowed_member_ids',
        store=True
    )
    
    # Dates
    date_start = fields.Date(
        string='Date de début',
        tracking=True,
        required=True
    )
    date_end = fields.Date(
        string='Date de fin',
        tracking=True
    )
    
    # Notes
    notes = fields.Html(
        string='Notes',
        tracking=True,
        sanitize=True,
        strip_style=True
    )

    # Contraintes SQL
    _sql_constraints = [
        ('unique_code_company', 
         'UNIQUE(code, company_id)', 
         'Le code doit être unique par société'),
        ('check_dates', 
         'CHECK(date_start <= date_end OR date_end IS NULL)', 
         'La date de début doit être antérieure à la date de fin')
    ]

    # Méthodes de calcul
    @api.depends('member_ids')
    def _compute_member_count(self):
        for record in self:
            record.member_count = len(record.member_ids)

    @api.depends('parent_id', 'parent_id.member_ids')
    def _compute_allowed_member_ids(self):
        for groupment in self:
            if groupment.parent_id:
                groupment.allowed_member_ids = groupment.parent_id.member_ids
            else:
                groupment.allowed_member_ids = self.env['res.partner']

    # Contraintes Python
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end and record.date_start > record.date_end:
                raise ValidationError(_("La date de début doit être antérieure à la date de fin"))

    # Actions
    def action_activate(self):
        for record in self:
            if not record.member_ids:
                raise UserError(_("Ajoutez au moins un membre avant d'activer le groupement."))
            if not record.agent_id:
                raise UserError(_("Définissez un agent avant d'activer le groupement."))
            record.state = 'active'

    def action_deactivate(self):
        self.write({'state': 'inactive'})

    def action_draft(self):
        self.write({'state': 'draft'})

    # Surcharges ORM
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('partner.groupment')
        return super().create(vals_list)