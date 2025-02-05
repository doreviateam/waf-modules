from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class PartnerInterest(models.Model):
    _name = 'partner.interest'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Centre d'intérêt partenaire"
    _order = 'sequence, name'
    _check_company_auto = True

    # Champs techniques
    sequence = fields.Integer(
        string='Séquence',
        default=10,
        help="Définit l'ordre d'affichage",
        tracking=True
    )
    active = fields.Boolean(
        string='Actif',
        default=True,
        tracking=True,
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True
    )

    # Champs d'identification
    name = fields.Char(
        string='Nom',
        required=True,
        translate=True,
        tracking=True,
        index='btree'
    )
    code = fields.Char(
        string='Code',
        copy=False,
        tracking=True,
        index='btree'
    )
    display_name = fields.Char(
        string='Nom affiché',
        compute='_compute_display_name',
        store=True
    )

    # Champs descriptifs
    description = fields.Html(
        string='Description',
        translate=True,
        tracking=True,
        sanitize=True,
        strip_style=True
    )

    # Relations
    groupment_ids = fields.One2many(
        'partner.groupment',
        'interest_id',
        string='Groupements',
        context={'active_test': False}
    )
    user_ids = fields.Many2many(
        'res.users',
        string='Utilisateurs autorisés',
        default=lambda self: self.env.user,
        context={'active_test': False},
        tracking=True
    )

    # Statistiques
    groupment_count = fields.Integer(
        string='Nombre de groupements',
        compute='_compute_groupment_counts',
        compute_sudo=True
    )
    active_groupment_count = fields.Integer(
        string='Groupements actifs',
        compute='_compute_groupment_counts',
        compute_sudo=True
    )

    # Contraintes SQL
    _sql_constraints = [
        ('code_company_uniq',
         'UNIQUE(code, company_id)',
         'Le code doit être unique par société'),
        ('name_company_uniq',
         'UNIQUE(name, company_id)',
         'Le nom doit être unique par société')
    ]

    # Méthodes calculées
    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f'[{record.code}] {record.name}' if record.code else record.name

    @api.depends('groupment_ids', 'groupment_ids.active')
    def _compute_groupment_counts(self):
        for record in self:
            groupements = record.with_context(active_test=False).groupment_ids
            record.groupment_count = len(groupements)
            record.active_groupment_count = len(groupements.filtered('active'))

    # Surcharges ORM
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('partner.interest')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code') == '':
            vals['code'] = self.env['ir.sequence'].next_by_code('partner.interest')
        return super().write(vals)

    def unlink(self):
        if self.mapped('groupment_ids'):
            raise UserError(_("Impossible de supprimer un type d'intérêt lié à des groupements"))
        return super().unlink()

    def copy(self, default=None):
        default = dict(default or {})
        default['code'] = self.env['ir.sequence'].next_by_code('partner.interest')
        return super().copy(default)

    # Actions
    def action_view_groupments(self):
        self.ensure_one()
        return {
            'name': _('Groupements'),
            'type': 'ir.actions.act_window',
            'res_model': 'partner.groupment',
            'view_mode': 'tree,form',
            'domain': [('interest_id', '=', self.id)],
            'context': {'default_interest_id': self.id}
        }