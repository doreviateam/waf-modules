# -*- coding: utf-8 -*-
###############################################################################
#
#    Dorevia
#    Copyright (C) 2025 Dorevia (<https://www.doreviateam.com>).
#
###############################################################################
"""
Extension du modèle res.partner pour la gestion de la localisation.

Ce module ajoute des fonctionnalités de localisation spécifiques :
- Gestion des départements français
- Gestion des régions
- Détection automatique du département selon le code postal
"""

from odoo import models, fields, api


# class ResRegion(models.Model):
#     _name = 'res.region'
#     _description = 'Region'

#     name = fields.Char(string='Nom', required=True)
#     code = fields.Char(string='Code', required=True)
#     country_id = fields.Many2one('res.country', string='Pays', required=True)
#     active = fields.Boolean(string='Actif', default=True)


class ResPartnerLocation(models.Model):
    _inherit = 'res.partner'

    #
    # Champs de localisation
    #
    department_id = fields.Many2one(
        'res.country.department',
        string='Département',
        domain="[('country_id.code', '=', 'FR')]",
        help="Département français du partenaire",
    )

    state_id = fields.Many2one(
        'res.country.state',
        string='Région',
        related='department_id.state_id',
        store=True,
        readonly=True,
        help="Région française du partenaire, déduite du département",
    )

    #
    # Onchange et calculs automatiques
    #
    @api.onchange('department_id')
    def _onchange_department_id(self):
        """Met à jour le pays et la région en fonction du département sélectionné."""
        if self.department_id:
            self.country_id = self.department_id.country_id
            self.state_id = self.department_id.state_id

    @api.onchange('zip', 'country_id')
    def _onchange_zip_country(self):
        """Détecte automatiquement le département à partir du code postal français."""
        if self.country_id.code == 'FR' and self.zip and len(self.zip) == 5:
            dept_code = self.zip[:2]
            
            # Cas spéciaux
            if dept_code == '20':  # Corse
                dept_code = '2A' if self.zip[:3] <= '201' else '2B'
            elif dept_code in ['97', '98']:  # DOM-TOM
                dept_code = self.zip[:3]
            
            department = self.env['res.country.department'].search([
                ('code', '=', dept_code),
                ('country_id.code', '=', 'FR')
            ], limit=1)
            
            if department:
                self.department_id = department.id 