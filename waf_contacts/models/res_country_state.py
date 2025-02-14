from odoo import models, fields, api

class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    region_id = fields.Many2one(
        'res.country.state',
        string='Région administrative',
        domain=[('type', '=', 'region')]
    )

    parent_id = fields.Many2one(
        'res.country.state',
        string='Région parente',
        domain="[('country_id', '=', country_id), ('is_region', '=', True)]")
    child_ids = fields.One2many('res.country.state', 'parent_id', string='Départements')
    is_region = fields.Boolean(string="Est une région", compute='_compute_is_region', store=True)
    is_department = fields.Boolean('Est un département', compute='_compute_is_department', store=True)
    
    @api.depends('parent_id', 'is_region', 'is_department')
    def _compute_region_id(self):
        """Calcule la région associée à l'état"""
        for record in self:
            if record.is_region:
                record.region_id = record.id
            elif record.is_department and record.parent_id:
                record.region_id = record.parent_id.id
            else:
                record.region_id = False

    @api.depends('parent_id')
    def _compute_is_department(self):
        for record in self:
            record.is_department = bool(record.parent_id)

    @api.depends('code', 'country_id')
    def _compute_is_region(self):
        for state in self:
            # On vérifie d'abord que c'est bien un état français
            if state.country_id.code == 'FR':
                # Si le code contient uniquement des lettres et fait 3 caractères, c'est une région
                state.is_region = state.code and len(state.code) == 3 and state.code.isalpha()
            else:
                state.is_region = False 