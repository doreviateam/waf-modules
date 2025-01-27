# -*- coding: utf-8 -*-
###############################################################################
#
#    Dorevia
#    Copyright (C) 2025 Dorevia (<https://www.doreviateam.com>).
#
###############################################################################
"""
Gestion des badges pour les partenaires.

Ce module permet de gérer les badges qui peuvent être attribués aux partenaires,
notamment :
- La définition des badges (nom, description, couleur)
- L'association des badges aux partenaires
"""

from odoo import models, fields, api


class ResPartnerBadge(models.Model):
    _name = 'res.partner.badge'
    _description = 'Badge pour les partenaires'

    #
    # Champs
    #
    name = fields.Char(string='Nom', required=True, help="Nom du badge")
    active = fields.Boolean(string='Actif', default=True, help="Active le badge")
    description = fields.Text(string='Description', help="Description du badge")
    color = fields.Char(string='Couleur', help="Couleur du badge")
    partner_ids = fields.Many2many(comodel_name='res.partner', relation='res_partner_badge_rel', column1='badge_id', column2='partner_id', 
                                   string='Partenaires', help="Partenaires associés au badge")
    
    
class ResPartner(models.Model):
    _inherit = 'res.partner'

    badge_ids = fields.Many2many(comodel_name='res.partner.badge', relation='res_partner_badge_rel', column1='partner_id', column2='badge_id', 
                                 string='Badges', help="Badges associés au partenaire")
    # Calcule l'attribution de badge en fontion de la relation hierarchique entre une entité et sa mère 
    company_badge_display = fields.Char(string='Badge', compute='_compute_company_badge_display', store=True, index=True, help="Badge de l'entité")
    badge_color = fields.Char(string='Couleur du badge', compute='_compute_company_badge_display', store=True)
    
    hierarchy_relation = fields.Selection([ # OK
        ('other', 'Autre'),
        ('agency', 'Agence'),
        ('headquarters', 'Siège')
    ], string='Établissement', 
       default='other',
       help="Définit le type d'établissement dans la structure organisationnelle :\n"
            "* Établissement principal : Siège de l'entreprise\n"
            "* Établissement secondaire : Agence ou succursale\n"
            "* Autre établissement : Autre type de structure\n\n"
            "Note : Ce type est différent des types d'adresses standards qui servent à la logistique et l'administration.")


    @api.depends('parent_id', 'child_ids', 'hierarchy_relation', 'parent_id.hierarchy_relation')
    def _compute_company_badge_display(self):
        """Permet de définir les badges en fonction de la relation hierarchique"""
        for record in self:
            # Maison mère : pas de parent, avec enfants, type 'other'
            if not record.parent_id and record.child_ids and record.hierarchy_relation == 'other':
                record.company_badge_display = 'Maison mère'
                record.badge_color = 'primary'  # Bleu

            # Filiale : parent type 'other', type 'other'
            elif record.parent_id and record.parent_id.hierarchy_relation == 'other' and record.hierarchy_relation == 'other':
                record.company_badge_display = 'Filiale'
                record.badge_color = 'success'  # Vert

            # Siège : parent type 'other', type 'headquarters'
            elif record.parent_id and record.parent_id.hierarchy_relation == 'other' and record.hierarchy_relation == 'headquarters':
                record.company_badge_display = 'Siège'
                record.badge_color = 'warning'  # Orange

            # Agence : parent type 'other', type 'agency'
            elif record.parent_id and record.parent_id.hierarchy_relation == 'headquarters' and record.hierarchy_relation == 'agency':
                record.company_badge_display = 'Agence'
                record.badge_color = 'info'  # Bleu clair

            # Antenne : parent type 'headquarters', type 'agency'
            elif record.parent_id and record.parent_id.hierarchy_relation == 'headquarters' and record.hierarchy_relation == 'headquarters':
                record.company_badge_display = 'Antenne'
                record.badge_color = 'warning'  # C'est un siège qui est piloté par un autre siège

            else:
                record.company_badge_display = False
                record.badge_color = False