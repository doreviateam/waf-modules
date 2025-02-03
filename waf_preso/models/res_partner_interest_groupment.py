from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResPartnerInterestGroupment(models.Model):
    _name = 'res.partner.interest.groupment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Groupement d'intérêt"
    _order = 'name'
    _rec_name = 'name'
    _sql_constraints = [
        ('partner_sale_unique', 
         'UNIQUE(partner_id, sale_order_id)',
         'Un partenaire ne peut être qu\'une seule fois dans un groupement pour une même commande!')
    ]

    name = fields.Char(
        string='Nom', 
        required=True, 
        index=True, 
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ],
        string='État',
        default='draft',
        tracking=True,
        required=True,
        index=True
    )
    active = fields.Boolean(default=True)
    date_start = fields.Date(
        string='Date de début',
        required=True,
        default=fields.Date.context_today
    )
    date_end = fields.Date(string='Date de fin')
    agent_id = fields.Many2one(
        'res.partner',
        string='Mandataire',
        required=True,
        tracking=True,
        domain=[('is_company', '=', True)],
        help="Société mandataire du groupement"
    )
    interest_type_id = fields.Many2one(
        'res.partner.interest.type',
        string="Type d'intérêt",
        required=True
    )
    member_ids = fields.Many2many(
        'res.partner', 
        string='Membres', 
        tracking=True
    )
    member_count = fields.Integer(
        compute='_compute_member_count', 
        store=True
    )
    sale_order_ids = fields.One2many(
        'sale.order',
        'interest_groupment_id',
        string='Commandes'
    )
    sale_order_count = fields.Integer(
        string='Nombre de commandes', 
        compute='_compute_sale_order_count', 
        store=True
    )
    color = fields.Integer(string='Couleur')
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        index=True
    )
    notes = fields.Text(string='Notes')

    @api.constrains('agent_id')
    def _check_agent_company(self):
        for record in self:
            if not record.agent_id.is_company:
                raise ValidationError(_("Le mandataire doit être une société"))

    @api.constrains('member_ids', 'agent_id')
    def _check_members_and_agent(self):
        for record in self:
            if record.agent_id in record.member_ids:
                raise ValidationError(_("Le mandataire ne peut pas être membre de son propre groupement"))
            if len(record.member_ids) < 2:
                raise ValidationError(_("Un groupement doit avoir au moins 2 membres"))

    @api.depends('sale_order_ids')
    def _compute_sale_order_count(self):
        """Calcule le nombre de commandes liées"""
        for groupment in self:
            groupment.sale_order_count = len(groupment.sale_order_ids)

    def action_view_orders(self):
        self.ensure_one()
        return {
            'name': _('Commandes'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('interest_groupment_id', '=', self.id)],
            'context': {'default_interest_groupment_id': self.id}
        }

    @api.depends('member_ids')
    def _compute_member_count(self):
        for record in self:
            record.member_count = len(record.member_ids)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end and record.date_start > record.date_end:
                raise ValidationError(_("La date de fin doit être postérieure à la date de début."))
