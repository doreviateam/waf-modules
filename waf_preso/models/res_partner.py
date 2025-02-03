from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    interest_group_ids = fields.One2many(
        'res.partner.interest.groupment', 
        'agent_id', 
        domain="[('state', '=', 'active')]"
    )
    managed_groupment_ids = fields.One2many(
        'res.partner.interest.groupment', 
        'agent_id', 
        string='Groupements gérés'
    )
    member_groupment_ids = fields.Many2many(
        'res.partner.interest.groupment', 
        'res_partner_interest_groupment_member_rel',
        'partner_id', 
        'groupment_id',
        string='Membre des groupements'
    )
    interest_group_count = fields.Integer(
        string='Nombre de groupements', 
        compute='_compute_interest_group_count'
    )
    region_id = fields.Many2one('res.region', string='Région')
    state_id = fields.Many2one('res.country.state', string='État/Province')

    interest_groupment_ids = fields.One2many(
        'res.partner.interest.groupment',
        'partner_id',
        string="Groupements d'intérêt"
    )

    interest_groupment_count = fields.Integer(
        string="Nombre de groupements",
        compute='_compute_interest_groupment_count',
        store=True
    )

    @api.depends('managed_groupment_ids', 'member_groupment_ids')
    def _compute_interest_group_count(self):
        """Optimisé avec des requêtes directes."""
        for partner in self:
            partner.interest_group_count = (
                self.env['res.partner.interest.groupment'].search_count([
                    ('agent_id', '=', partner.id)
                ]) + len(partner.member_groupment_ids)
            )

    @api.constrains('agent_id')
    def _check_groupment_constraints(self):
        for partner in self:
            if partner.agent_id and not partner.agent_id.is_company:
                raise ValidationError("Le mandataire doit être une société")

    def action_view_interest_groupments(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('waf_preso.action_interest_groupment')
        action['domain'] = ['|', ('agent_id', '=', self.id), ('member_ids', 'in', self.id)]
        return action

    @api.depends('interest_groupment_ids')
    def _compute_interest_groupment_count(self):
        for record in self:
            record.interest_groupment_count = len(record.interest_groupment_ids)