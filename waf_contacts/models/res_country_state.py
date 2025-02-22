from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class ResCountryState(models.Model):
    _inherit = 'res.country.state'
    _description = 'Gestion des régions et départements français'
    _order = 'country_id, is_region desc, code'

    # Champs de base
    region_id = fields.Many2one(
        'res.country.state',
        string='Région administrative',
        domain="[('is_region', '=', True)]",
        index=True,
        ondelete='restrict'
    )

    parent_id = fields.Many2one(
        'res.country.state',
        string='Région parente',
        domain="[('country_id', '=', country_id), ('is_region', '=', True)]",
        index=True,
        ondelete='restrict'
    )
    
    child_ids = fields.One2many(
        'res.country.state', 
        'parent_id', 
        string='Départements'
    )

    # Champs calculés
    is_region = fields.Boolean(
        string="Est une région", 
        compute='_compute_is_region', 
        store=True,
        index=True
    )
    
    is_department = fields.Boolean(
        string='Est un département', 
        compute='_compute_is_department', 
        store=True,
        index=True
    )

    department_count = fields.Integer(
        string='Nombre de départements',
        compute='_compute_department_count',
        store=True
    )

    # Champs additionnels
    insee_code = fields.Char(
        string='Code INSEE',
        size=3,
        help="Code INSEE de la région ou du département"
    )
    
    population = fields.Integer(
        string='Population',
        help="Population selon le dernier recensement"
    )
    
    surface = fields.Float(
        string='Superficie (km²)',
        digits=(10, 2)
    )

    active = fields.Boolean(
        default=True,
        help="Permet de masquer la région/département sans la supprimer."
    )

    # Compute methods
    @api.depends('parent_id')
    def _compute_is_department(self):
        for record in self:
            record.is_department = bool(record.parent_id)

    @api.depends('code', 'country_id')
    def _compute_is_region(self):
        for state in self:
            state.is_region = (
                state.country_id.code == 'FR' and 
                state.code and 
                len(state.code) == 3 and 
                state.code.isalpha()
            )

    @api.depends('is_region', 'is_department', 'parent_id')
    def _compute_region_id(self):
        for record in self:
            record.region_id = (
                record.id if record.is_region
                else record.parent_id.id if record.is_department
                else False
            )

    @api.depends('child_ids')
    def _compute_department_count(self):
        for record in self:
            record.department_count = len(record.child_ids)

    # Contraintes
    @api.constrains('parent_id')
    def _check_parent_id(self):
        for record in self:
            if record.parent_id:
                if record.parent_id == record:
                    raise ValidationError(_("Une région/département ne peut pas être son propre parent!"))
                if not record.parent_id.is_region:
                    raise ValidationError(_("Le parent doit être une région!"))

    @api.constrains('insee_code')
    def _check_insee_code(self):
        for record in self:
            if record.insee_code:
                if not re.match(r'^[0-9]{2,3}$', record.insee_code):
                    raise ValidationError(_("Le code INSEE doit contenir 2 ou 3 chiffres!"))

    # Contraintes SQL
    _sql_constraints = [
        ('unique_code_per_country', 
         'UNIQUE(code, country_id)',
         'Le code doit être unique par pays!'),
        ('unique_insee_code', 
         'UNIQUE(insee_code)',
         'Le code INSEE doit être unique!'),
    ]

    # Surcharge des méthodes standard
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.code} - {record.name}"
            if record.is_department and record.parent_id:
                name = f"{name} ({record.parent_id.code})"
            result.append((record.id, name))
        return result

    @api.model
    def create(self, vals):
        if vals.get('code'):
            vals['code'] = vals['code'].upper()
        return super().create(vals)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = vals['code'].upper()
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.child_ids:
                raise ValidationError(_(
                    "Impossible de supprimer %(record)s car il a des départements associés!",
                    record=record.name
                ))
        return super().unlink()