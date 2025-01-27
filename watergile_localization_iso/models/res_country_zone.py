from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class CountryZone(models.Model):
    _name = 'res.country.zone'
    _description = 'Zone géographique'

    name = fields.Char(
        string='Nom',
        required=True,
        help="Nom de la zone géographique"
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        help="Code unique de la zone (2-3 caractères en majuscules)"
    )
    
    description = fields.Text(
        string='Description',
        help="Description détaillée de la zone"
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help="Permet de masquer la zone sans la supprimer"
    )
    
    country_ids = fields.Many2many(
        'res.country',
        string='Pays',
        help="Pays appartenant à cette zone"
    )

    _sql_constraints = [
        ('unique_code', 'UNIQUE(code)', 
         'Le code de la zone doit être unique !')
    ]

    @api.constrains('code')
    def _check_code_format(self):
        """Vérifie le format du code de la zone"""
        for record in self:
            if not record.code:
                raise ValidationError(_("Le code de la zone est obligatoire."))
            
            if not 2 <= len(record.code) <= 3:
                raise ValidationError(_(
                    "Le code de la zone doit contenir entre 2 et 3 caractères "
                    "(actuellement: %s caractères)") % len(record.code)
                )
            
            if not re.match("^[A-Z]+$", record.code):
                raise ValidationError(_(
                    "Le code de la zone doit être en majuscules "
                    "(code invalide: %s)") % record.code
                )

    @api.constrains('name')
    def _check_name(self):
        """Vérifie que le nom n'est pas vide"""
        for record in self:
            if not record.name or not record.name.strip():
                raise ValidationError(_("Le nom de la zone est obligatoire."))

    def unlink(self):
        """Empêche la suppression d'une zone contenant des pays"""
        for record in self:
            if record.country_ids:
                raise ValidationError(_(
                    "Impossible de supprimer la zone '%s' car elle contient des pays. "
                    "Veuillez d'abord retirer tous les pays de la zone.") % record.name
                )
        return super().unlink()

    def name_get(self):
        """Personnalise l'affichage du nom de la zone"""
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}"
            result.append((record.id, name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """Permet la recherche par code ou nom"""
        args = args or []
        domain = []
        
        if name:
            domain = ['|',
                     ('code', operator, name),
                     ('name', operator, name)]
            
        return self._search(domain + args, limit=limit)