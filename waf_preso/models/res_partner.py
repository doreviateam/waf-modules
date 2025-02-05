from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Champs de groupement
    groupment_ids = fields.Many2many(
        'partner.groupment',
        string='Groupements',
        relation='partner_groupment_member_rel',
        column1='partner_id',
        column2='groupment_id',
        tracking=True,
        domain="[('state', '=', 'active')]",
        help="Groupements dont ce partenaire est membre"
    )

    managed_groupment_ids = fields.One2many(
        'partner.groupment',
        'agent_id',
        string='Groupements gérés',
        help="Groupements dont ce partenaire est l'agent"
    )

    # Champs calculés
    groupment_count = fields.Integer(
        string='Nombre de groupements',
        compute='_compute_groupment_count',
        store=True,
        help="Nombre total de groupements (membre + gérés)"
    )

    is_agent = fields.Boolean(
        string="Est un agent",
        compute='_compute_is_agent',
        store=True,
        index=True,
        help="Indique si le partenaire est agent de groupements"
    )

    managed_partner_ids = fields.Many2many(
        'res.partner',
        string='Partenaires gérés',
        compute='_compute_managed_partner_ids',
        compute_sudo=True,
        help="Partenaires membres des groupements gérés"
    )

    managed_partner_count = fields.Integer(
        string='Nombre de partenaires gérés',
        compute='_compute_managed_partner_ids',
        store=True,
        help="Nombre de partenaires membres des groupements gérés"
    )

    # Méthodes calculées
    @api.depends('managed_groupment_ids')
    def _compute_is_agent(self):
        """Détermine si le partenaire est un agent"""
        for partner in self:
            partner.is_agent = bool(partner.managed_groupment_ids)

    @api.depends('groupment_ids', 'managed_groupment_ids')
    def _compute_groupment_count(self):
        """Calcule le nombre total de groupements"""
        for partner in self:
            partner.groupment_count = len(partner.groupment_ids) + len(partner.managed_groupment_ids)

    @api.depends('managed_groupment_ids.member_ids')
    def _compute_managed_partner_ids(self):
        """Calcule la liste des partenaires gérés et leur nombre"""
        for partner in self:
            partner.managed_partner_ids = partner.managed_groupment_ids.mapped('member_ids')
            partner.managed_partner_count = len(partner.managed_partner_ids)

    # Contraintes
    @api.constrains('groupment_ids', 'is_company')
    def _check_groupment_company(self):
        """Vérifie que seules les sociétés peuvent être membres de groupements"""
        for partner in self:
            if partner.groupment_ids and not partner.is_company:
                raise ValidationError(_("Seules les sociétés peuvent être membres de groupements."))

    # Actions
    def action_view_groupments(self):
        """Ouvre la vue des groupements liés au partenaire"""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('waf_preso.action_partner_groupment')
        action.update({
            'domain': ['|', 
                ('member_ids', 'in', self.id),
                ('agent_id', '=', self.id)
            ],
            'context': {'default_agent_id': self.id if self.is_agent else False}
        })
        return action

    def action_view_managed_partners(self):
        """Ouvre la vue des partenaires gérés"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Partenaires gérés'),
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.managed_partner_ids.ids)],
            'context': {
                'default_agent_id': self.id,
                'search_default_active': 1
            }
        }