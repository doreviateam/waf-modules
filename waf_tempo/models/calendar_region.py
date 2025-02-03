from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class CalendarRegion(models.Model):
    _name = 'calendar.region'
    _description = 'Région du calendrier'
    _order = 'country_id, name'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nom', required=True, tracking=True, translate=True, help="Nom de la région")
    code = fields.Char(string='Code', required=True, tracking=True, help="Code unique de la région (ex: GP, MQ...)")
    country_id = fields.Many2one(comodel_name='res.country', string='Pays', required=True, tracking=True, help="Pays de la région")
    active = fields.Boolean(default=True, tracking=True, help="Indique si la région est active")
    description = fields.Text(string='Description', translate=True, help="Description détaillée de la région")
    specific_holiday_ids = fields.One2many(comodel_name='calendar.holiday', inverse_name='region_id', string='Jours fériés spécifiques', help="Jours fériés spécifiques à cette région")
    display_name = fields.Char(string='Nom complet', compute='_compute_display_name', store=True)

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Le code de la région doit être unique !'),
        ('unique_country_code', 'unique(country_id, code)', 'Une seule région par code et pays !')
    ]

    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if record.code and record.code != record.code.upper():
                record._cr.execute('UPDATE calendar_region SET code = %s WHERE id = %s',
                                 (record.code.upper(), record.id))
                record.invalidate_cache(['code'])

    @api.depends('name', 'code', 'country_id.name')
    def _compute_display_name(self):
        for record in self:
            name = f"{record.name} ({record.code})"
            if record.country_id:
                name = f"{name} - {record.country_id.name}"
            record.display_name = name

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|',
                ('name', operator, name),
                ('code', operator, name),
                ('country_id.name', operator, name)
            ]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)