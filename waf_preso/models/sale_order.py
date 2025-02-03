from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    agent_id = fields.Many2one(
        'res.partner',
        string='Mandataire',
        domain="[('is_company', '=', True)]",
        groups="sales_team.group_sale_salesman"
    )
    interest_groupment_ids = fields.One2many(
        'res.partner.interest.groupment',
        'sale_order_id',
        string="Groupements d'intérêt"
    )
    interest_groupment_count = fields.Integer(
        string="Nombre de groupements",
        compute='_compute_interest_groupment_count',
        store=True
    )
    interest_groupment_id = fields.Many2one(
        'res.partner.interest.groupment',
        string="Groupement d'intérêt",
        ondelete='restrict'
    )

    @api.constrains('agent_id', 'company_id')
    def _check_agent_company(self):
        for record in self:
            if record.agent_id.company_id != record.company_id:
                raise ValidationError("Le mandataire doit appartenir à la même société")

    @api.depends('interest_groupment_ids')
    def _compute_interest_groupment_count(self):
        for record in self:
            record.interest_groupment_count = len(record.interest_groupment_ids)

    def action_view_groupments(self):
        self.ensure_one()
        return {
            'name': ('Groupements'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'res.partner.interest.groupment',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }