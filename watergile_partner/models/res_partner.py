# -*- coding: utf-8 -*-
###############################################################################
#
#    Dorevia
#    Copyright (C) 2025 Dorevia (<https://www.doreviateam.com>).
#
###############################################################################
"""
Extension du modèle res.partner.

Ce module étend les fonctionnalités des partenaires pour gérer :
- Les badges et leur affichage
- Les relations hiérarchiques entre entités
- La synchronisation des adresses
- Les types d'établissements
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    #
    # Champs de base
    #
    type = fields.Selection(
        selection_add=[
            ('contact', 'Contact'),
            ('invoice', 'Invoice Address'),
            ('delivery', 'Delivery Address'),
            ('other', 'Other Address'),
            ('private', 'Private Address'),
        ],
        ondelete={
            'contact': 'set default',
            'invoice': 'set default',
            'delivery': 'set default',
            'other': 'set default',
            'private': 'set default',
        }
    )

    #
    # Champs organisationnels
    #
    hierarchy_relation = fields.Selection([
        ('other', 'Autre'),
        ('agency', 'Agence'),
        ('headquarters', 'Siège')
    ], string='Établissement',
       default='other',
       help="Définit le type d'établissement dans la structure organisationnelle")

    relation_description = fields.Char(
        string="Description de la relation",
        help="Description complémentaire de la relation"
    )

    #
    # Champs de badge
    #
    badge_ids = fields.Many2many(
        comodel_name='res.partner.badge',
        relation='res_partner_badge_rel',
        column1='partner_id',
        column2='badge_id',
        string='Badges',
        help="Badges associés au partenaire"
    )

    company_badge_display = fields.Char(
        string='Badge',
        compute='_compute_company_badge_display',
        store=True,
        help="Badge de l'entité"
    )

    badge_color = fields.Char(
        string='Couleur du badge',
        compute='_compute_company_badge_display',
        store=True
    )

    #
    # Champs de blaz
    #
    partner_blaz_id = fields.Many2one('partner.blaz', string='Blaz', 
                                    required=False)  # Optionnel par défaut

    #
    # Méthodes de calcul
    #
    @api.depends('parent_id', 'child_ids', 'hierarchy_relation', 'parent_id.hierarchy_relation')
    def _compute_company_badge_display(self):
        """Calcul des badges en fonction de la hiérarchie"""
        for record in self:
            if record.parent_id and record.parent_id.hierarchy_relation == 'other' and record.hierarchy_relation == 'other':
                record.company_badge_display = 'Filiale'
                record.badge_color = 'success'
            else:
                record.company_badge_display = False
                record.badge_color = False

    #
    # Surcharges des méthodes standard
    #
    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la création pour attribuer automatiquement le blaz aux sociétés."""
        # Désactiver temporairement la contrainte pour la création
        self = self.with_context(skip_blaz_check=True)
        partners = super().create(vals_list)
        
        # Créer les blaz après la création des partenaires
        for partner in partners:
            if partner.is_company and not partner.partner_blaz_id:
                # Créer automatiquement un blaz pour la société
                blaz = self.env['partner.blaz'].create({
                    'name': partner.name,
                    'owner_partner_id': partner.id,
                    'image_1920': partner.image_1920
                })
                partner.partner_blaz_id = blaz.id
        
        return partners

    def write(self, vals):
        """Override pour empêcher la synchronisation d'adresse pour les sociétés"""
        if self.is_company and 'parent_id' in vals:
            # Sauvegarde des valeurs d'adresse actuelles
            address_fields = ['street', 'street2', 'city', 'state_id', 'zip', 'country_id']
            current_values = {field: self[field] for field in address_fields if self[field]}
            
            # Exécution du write standard
            result = super().write(vals)
            
            # Restauration des valeurs d'adresse pour les sociétés
            if current_values:
                super().write(current_values)
            return result
            
        return super().write(vals)

    #
    # Méthodes techniques
    #
    @api.model
    def _valid_field_parameter(self, field, name):
        """Permet de définir les paramètres des champs"""
        return name in ['widget', 'options'] or super()._valid_field_parameter(field, name)

    def _sync_parent_address(self, parent):
        """Méthode utilitaire pour synchroniser l'adresse avec le parent"""
        return {
            'street': parent.street,
            'street2': parent.street2,
            'city': parent.city,
            'zip': parent.zip,
            'state_id': parent.state_id.id,
            'country_id': parent.country_id.id,
        }

    #
    # Onchange
    #
    @api.onchange('parent_id')
    def onchange_parent_id(self):
        """Override pour empêcher la copie automatique de l'adresse du parent pour les sociétés"""
        if not self.is_company:
            # Pour les contacts, on garde le comportement standard
            result = super().onchange_parent_id()
            # On définit le type par défaut à 'delivery' pour les nouveaux contacts
            if not self.type and self.parent_id:
                self.type = 'delivery'
            return result
        # Pour les sociétés, on ne fait rien
        return {}

    @api.onchange('type')
    def onchange_type(self):
        """Empêcher la copie automatique de l'adresse pour les sociétés"""
        if self.is_company:
            return {}
        # Pour les contacts, on copie l'adresse du parent si nécessaire
        if self.parent_id and self.type in ['invoice', 'delivery', 'other']:
            addr = self.parent_id.address_get([self.type])
            if addr[self.type]:
                self.update(self._sync_parent_address(addr[self.type]))
        return {}

    # Garder ces champs existants
    department_id = fields.Many2one(
        'res.country.department',
        string='Département',
        domain="[('country_id.code', '=', 'FR')]"
    )

    state_id = fields.Many2one('res.country.state', string='Région', related='department_id.state_id', store=True,
        readonly=True
    )

    country_id = fields.Many2one(
        'res.country', 
        string='Pays',
        required=True,
        default=lambda self: self.env['res.country'].search([('code', '=', 'FR')], limit=1)
    )

    @api.onchange('department_id')
    def _onchange_department_id(self):
        """Permet de définir les paramètres des champs"""
        if self.department_id:
            self.country_id = self.department_id.country_id
            self.state_id = self.department_id.state_id

    @api.onchange('zip', 'country_id')
    def _onchange_zip_country(self):
        """Permet de définir le département automatiquement"""
        if self.zip and len(self.zip) == 5:
            dept_code = self.zip[:2]
            
            # Cas spécial de la Corse
            if dept_code == '20':
                dept_code = '2A' if self.zip[:3] <= '201' else '2B'
            
            # Pour les DOM-TOM, on prend les 3 premiers caractères
            elif dept_code in ['97', '98']:
                dept_code = self.zip[:3]
            
            department = self.env['res.country.department'].search([
                ('code', '=', dept_code)
            ], limit=1)
            
            if department:
                self.department_id = department.id
                self.country_id = department.country_id.id
                self.state_id = department.state_id.id

    @api.constrains('partner_blaz_id', 'is_company')
    def _check_blaz_rules(self):
        """Vérifie les règles d'attribution des blaz."""
        if self.env.context.get('skip_blaz_check'):
            return
        
        for record in self:
            if record.is_company:
                if not record.partner_blaz_id:
                    raise ValidationError(_("Une société doit avoir un blaz"))
                if record.partner_blaz_id.owner_partner_id != record:
                    raise ValidationError(_("Une société ne peut utiliser que les blaz dont elle est propriétaire"))
            elif record.partner_blaz_id and record.parent_id and record.parent_id.is_company:
                same_blaz_partners = self.search([
                    ('partner_blaz_id', '=', record.partner_blaz_id.id),
                    ('parent_id', '=', record.parent_id.id),
                    ('id', '!=', record.id),
                    ('is_company', '=', False)
                ])
                if same_blaz_partners:
                    raise ValidationError(_("Ce blaz est déjà utilisé par un autre employé de la même société"))

    @api.model
    def default_get(self, fields_list):
        # Récupère les valeurs par défaut existantes
        defaults = super().default_get(fields_list)
        
        # Si le pays n'est pas déjà défini et que le champ est demandé
        if 'country_id' in fields_list and 'country_id' not in defaults:
            # Recherche l'ID de la France
            france = self.env['res.country'].search([('code', '=', 'FR')], limit=1)
            if france:
                defaults['country_id'] = france.id
        
        return defaults

    @api.constrains('is_company', 'country_id', 'zip')
    def _check_zip_required_for_french_company(self):
        for partner in self:
            if (partner.is_company and 
                partner.country_id.code == 'FR' and 
                not partner.zip):
                raise ValidationError(_("Le code postal est obligatoire pour une société française"))

            