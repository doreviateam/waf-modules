# -*- coding: utf-8 -*-
###############################################################################
#
#    Dorevia
#    Copyright (C) 2025 Dorevia (<https://www.doreviateam.com>).
#
###############################################################################
"""
Gestion des blaz (marques/enseignes) des partenaires.

Ce module permet de gérer les blaz et leurs associations avec les partenaires,
notamment :
- L'attribution des logos aux partenaires autorisés
- La gestion des propriétaires de blaz
- Les contraintes de hiérarchie
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PartnerBlaz(models.Model):
    _name = 'partner.blaz'
    _description = 'Partner Blaz'

    # Messages d'erreur
    ERROR_OWNER_TYPE = _("Le propriétaire du blaz doit être une société")
    ERROR_PARTNERS_HIERARCHY = _("Les partenaires doivent être rattachés à la maison mère propriétaire du blaz")

    #
    # Champs
    #
    name = fields.Char(string='Nom', required=True)
    active = fields.Boolean(string='Actif', default=True)
    force_logo_update = fields.Boolean(string='Forcer la mise à jour des logos', help='Si coché, le logo sera mis à jour pour tous les contacts autorisés, '
             'même s\'ils ont déjà un logo', default=False)
    partner_ids = fields.One2many(comodel_name='res.partner', inverse_name='partner_blaz_id', string='Partenaires')
    image_1920 = fields.Image(string='Logo', max_width=1920, max_height=1920, required=True)
    image_128 = fields.Image(string='Logo miniature', related='image_1920', max_width=128, max_height=128, store=True)
    owner_partner_id = fields.Many2one(comodel_name='res.partner', string='Propriétaire du blaz', required=True, domain="[('type', '=', 'parent_company')]", 
                                       help='Maison mère propriétaire de ce blaz')
    authorized_partner_ids = fields.Many2many(comodel_name='res.partner', relation='partner_blaz_authorized_partner_rel', column1='blaz_id', 
                                              column2='partner_id', string='Contacts autorisés')

    #
    # Méthodes de mise à jour des logos
    #
    def _update_partner_logos(self, partners):
        """
        Met à jour les logos des partenaires autorisés.
        :param partners: recordset des partenaires à mettre à jour
        """
        for partner in partners:
            partner.partner_blaz_id = self.id
            if not partner.image_1920 or self.force_logo_update:
                partner.image_1920 = self.image_1920

    #
    # Surcharges des méthodes standard
    #
    @api.model_create_multi
    def create(self, vals_list):
        """
        Surcharge de la création pour mettre à jour les logos des partenaires.
        """
        blazs = super().create(vals_list)
        for blaz in blazs:
            blaz._update_partner_logos(blaz.authorized_partner_ids)
        return blazs

    def write(self, vals):
        """
        Surcharge de l'écriture pour mettre à jour les logos si nécessaire.
        """
        result = super().write(vals)
        if 'authorized_partner_ids' in vals or 'image_1920' in vals:
            for blaz in self:
                blaz._update_partner_logos(blaz.authorized_partner_ids)
        return result

    #
    # Contraintes
    #
    @api.constrains('owner_partner_id')
    def _check_owner_type(self):
        """Vérifie que le propriétaire est bien une société."""
        for record in self:
            if record.owner_partner_id and not record.owner_partner_id.is_company:
                raise ValidationError(self.ERROR_OWNER_TYPE)

    @api.constrains('partner_ids', 'owner_partner_id')
    def _check_partners_hierarchy(self):
        """Vérifie que les partenaires sont rattachés au bon propriétaire."""
        for record in self:
            for partner in record.partner_ids:
                if partner.parent_id and partner.parent_id != record.owner_partner_id:
                    raise ValidationError(self.ERROR_PARTNERS_HIERARCHY)
                

# -*- coding: utf-8 -*-
###############################################################################
#
#    Dorevia
#    Copyright (C) 2025 Dorevia (<https://www.doreviateam.com>).
#
###############################################################################
"""
Gestion des blaz (marques/enseignes) des partenaires.

Ce module permet de gérer les blaz et leurs associations avec les partenaires,
notamment :
- L'attribution des logos aux partenaires autorisés
- La gestion des propriétaires de blaz
- Les contraintes de hiérarchie
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PartnerBlaz(models.Model):
    _name = 'partner.blaz'
    _description = 'Partner Blaz'

    # Messages d'erreur
    ERROR_OWNER_TYPE = _("Le propriétaire du blaz doit être une société")
    ERROR_PARTNERS_HIERARCHY = _("Les partenaires doivent être rattachés à la maison mère propriétaire du blaz")

    #
    # Champs
    #
    name = fields.Char(string='Nom', required=True)
    active = fields.Boolean(string='Actif', default=True)
    force_logo_update = fields.Boolean(string='Forcer la mise à jour des logos', help='Si coché, le logo sera mis à jour pour tous les contacts autorisés, '
             'même s\'ils ont déjà un logo', default=False)
    partner_ids = fields.One2many(comodel_name='res.partner', inverse_name='partner_blaz_id', string='Partenaires')
    image_1920 = fields.Image(string='Logo', max_width=1920, max_height=1920, required=True)
    image_128 = fields.Image(string='Logo miniature', related='image_1920', max_width=128, max_height=128, store=True)
    owner_partner_id = fields.Many2one(comodel_name='res.partner', string='Propriétaire du blaz', required=True, domain="[('type', '=', 'parent_company')]", 
                                       help='Maison mère propriétaire de ce blaz')
    authorized_partner_ids = fields.Many2many(comodel_name='res.partner', relation='partner_blaz_authorized_partner_rel', column1='blaz_id', 
                                              column2='partner_id', string='Contacts autorisés')

    #
    # Méthodes de mise à jour des logos
    #
    def _update_partner_logos(self, partners):
        """
        Met à jour les logos des partenaires autorisés.
        :param partners: recordset des partenaires à mettre à jour
        """
        for partner in partners:
            partner.partner_blaz_id = self.id
            if not partner.image_1920 or self.force_logo_update:
                partner.image_1920 = self.image_1920

    #
    # Surcharges des méthodes standard
    #
    @api.model_create_multi
    def create(self, vals_list):
        """
        Surcharge de la création pour mettre à jour les logos des partenaires.
        """
        blazs = super().create(vals_list)
        for blaz in blazs:
            blaz._update_partner_logos(blaz.authorized_partner_ids)
        return blazs

    def write(self, vals):
        """
        Surcharge de l'écriture pour mettre à jour les logos si nécessaire.
        """
        result = super().write(vals)
        if 'authorized_partner_ids' in vals or 'image_1920' in vals:
            for blaz in self:
                blaz._update_partner_logos(blaz.authorized_partner_ids)
        return result

    #
    # Contraintes
    #
    @api.constrains('owner_partner_id')
    def _check_owner_type(self):
        """Vérifie que le propriétaire est bien une société."""
        for record in self:
            if record.owner_partner_id and not record.owner_partner_id.is_company:
                raise ValidationError(self.ERROR_OWNER_TYPE)

    @api.constrains('partner_ids', 'owner_partner_id')
    def _check_partners_hierarchy(self):
        """Vérifie que les partenaires sont rattachés au bon propriétaire."""
        for record in self:
            for partner in record.partner_ids:
                if partner.parent_id and partner.parent_id != record.owner_partner_id:
                    raise ValidationError(self.ERROR_PARTNERS_HIERARCHY)