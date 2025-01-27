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

    region_id = fields.Many2one(comodel_name='res.region',  string='Région', ondelete='restrict', index=True, help="Région de l'entité")
    
    # Champs de base pour la localisation
    department_id = fields.Many2one(
        'res.country.department',
        string='Département',
        domain="[('country_id.code', '=', 'FR')]"
    )

    state_id = fields.Many2one(
        'res.country.state',
        string='Région',
        related='department_id.state_id',
        store=True,
        readonly=True
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


class ResRegion(models.Model):
    _name = 'res.region'
    _description = 'Region'

    name = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code', required=True)
    country_id = fields.Many2one('res.country', string='Pays', required=True)
    active = fields.Boolean(string='Actif', default=True)


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

    region_id = fields.Many2one(
        comodel_name='res.region',
        string='Région',
        ondelete='restrict',
        index=True,
        help="Région de l'entité",
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