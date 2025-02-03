from odoo import models, fields, api




class ResPartnerInterestType(models.Model):
    _name = 'res.partner.interest.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Type de groupement d'intérêt"
    _order = 'sequence, name'

   
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Nom', required=True, index=True, translate=True)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)
    groupment_ids = fields.One2many('res.partner.interest.groupment', 'interest_type_id', string='Groupements')
    groupment_count = fields.Integer(string='Nombre de groupements', compute='_compute_groupment_count')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    def action_view_groupments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Groupements',
            'res_model': 'res.partner.interest.groupment',
            'view_mode': 'tree,form',
            'domain': [('interest_type_id', '=', self.id)],
            'context': {'default_interest_type_id': self.id},
        }

    @api.depends('groupment_ids')
    def _compute_groupment_count(self):
        for record in self:
            record.groupment_count = self.env['res.partner.interest.groupment'].search_count([
                ('interest_type_id', '=', record.id)
            ])

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)', 'Le nom doit être unique par société !')
    ]