from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import time

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Champs métier
    insee_siret = fields.Char(string="SIRET", help="Numéro SIRET de l'établissement")
    insee_siren = fields.Char(string="SIREN", readonly=True, help="Identifiant SIREN (9 premiers chiffres du SIRET)")
    insee_enseigne = fields.Char(string="Enseigne commerciale", readonly=True, help="Enseigne commerciale de l'établissement")
    insee_tva = fields.Char(string="N° TVA", readonly=True, help="N° TVA de l'établissement")
    insee_activite_principale = fields.Char(string="Code NAF", readonly=True, help="Code NAF de l'activité principale de l'établissement")    
    last_insee_sync = fields.Datetime(string='Dernière synchronisation', readonly=True)
    
    # Champs de localisation & géolocalisation
    insee_latitude = fields.Float(string="Latitude", digits=(16, 5), readonly=True, help="Latitude de l'établissement")
    insee_longitude = fields.Float(string="Longitude", digits=(16, 5), readonly=True, help="Longitude de l'établissement")

    # Champs de contrôle du siret
    is_siret_valid = fields.Boolean(string='SIRET Valide', compute='_compute_siret_valid', store=False)
    ctrl_message = fields.Char(string='Message', compute='_compute_siret_valid', store=False)

    def _format_siret(self, siret):
        """Formater un numéro SIRET avec espaces"""
        if not siret:
            return False
            
        # Vérification des 14 chiffres
        cleaned = ''.join(filter(str.isdigit, siret))
        if len(cleaned) != 14:
            return False
            
        # Format: XXX XXX XXX XXXXX
        formatted = ''
        for i, char in enumerate(cleaned):
            if i in [3, 6, 9]:
                formatted += ' '
            formatted += char
            
        return formatted.strip()

    @api.model_create_multi
    def create(self, vals_list):
        """Synchronise siret lors de la création"""
        for vals in vals_list:
            if vals.get('insee_siret'):
                # Formatage pour insee_siret (avec espaces)
                vals['insee_siret'] = self._format_siret(vals['insee_siret'])
                # Formatage pour siret (14 digits sans espace)
                vals['siret'] = ''.join(filter(str.isdigit, vals['insee_siret']))
        return super().create(vals_list)

    def write(self, vals):
        """Synchronise siret lors de la modification"""
        if vals.get('insee_siret'):
            # Formatage pour insee_siret (avec espaces)
            vals['insee_siret'] = self._format_siret(vals['insee_siret'])
            # Formatage pour siret (14 digits sans espace)
            vals['siret'] = ''.join(filter(str.isdigit, vals['insee_siret']))
        return super().write(vals)
    
    @api.onchange('insee_siret')
    def _onchange_siret(self):
        """Synchronisation avec l'INSEE lors de la modification du SIRET"""
        self.ensure_one()
        if self.insee_siret:
            self.insee_siret = self._format_siret(self.insee_siret)
            self.siret = self.insee_siret

    @api.depends('insee_siret', 'is_company')
    def _compute_siret_valid(self):
        """Vérification de la validité du SIRET"""
        for record in self:
            # Si l'entité n'est pas une personne morale, on efface le SIRET
            if not record.is_company:
                record.insee_siret = False  # Utiliser False au lieu de ""
                record.siret = False
                record.is_siret_valid = False
                record.ctrl_message = ""
                return

            record.is_siret_valid = False
            record.ctrl_message = ""

            if not record.insee_siret:
                return

            # Nettoyage
            cleaned = ''.join(filter(str.isdigit, record.insee_siret or ''))
            
            # Vérification longueur
            if len(cleaned) != 14:
                record.is_siret_valid = False
                record.ctrl_message = "Le SIRET doit contenir 14 chiffres"
                raise ValidationError(record.ctrl_message)

            # Vérification du numéro de siret
            somme = 0
            for i, digit in enumerate(cleaned):
                digit = int(digit)
                if i % 2 == 0:
                    doubled = digit * 2
                    somme += doubled if doubled < 10 else doubled - 9
                else:
                    somme += digit

            record.is_siret_valid = (somme % 10 == 0)
            record.ctrl_message = "SIRET valide" if record.is_siret_valid else "SIRET invalide"

            if not record.is_siret_valid:
                raise UserError(record.ctrl_message)
            
    
    def _verify_siret_from_insee(self):
        """Vérifie et récupère les données INSEE à partir du SIRET"""
        self.ensure_one()
        
        if not self.siret:
            _logger.info("Pas de SIRET trouvé")
            return False
            
        try:
            # Création du service de synchronisation
            _logger.info(f"Tentative de sync pour SIRET: {self.siret}")
            sync_service = self.env['insee.sync.service'].create({
                'siret': self.siret
            })
            
            # Récupération des données
            company_data = sync_service.sync_company_data()
            _logger.info(f"Données reçues de l'INSEE: {company_data}")
            
            if company_data:
                # Mise à jour uniquement des champs insee_*
                vals = {
                    'insee_siren': company_data.get('siren'),
                    'insee_enseigne': company_data.get('enseigne'),
                    'insee_tva': company_data.get('tva'),
                    'insee_activite_principale': company_data.get('activity'),
                    'last_insee_sync': fields.Datetime.now(),
                }
                _logger.info(f"Mise à jour avec les valeurs: {vals}")
                self.write(vals)
                return True
            else:
                _logger.warning("Aucune donnée reçue de l'INSEE")
                
        except Exception as e:
            _logger.error(f"Erreur vérification INSEE: {str(e)}")
            return False
            
        return False

    def action_verify_siret_insee(self):
        """Action bouton pour vérifier et mettre à jour les données INSEE"""
        self.ensure_one()
        
        if not self.siret:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _('SIRET manquant'),
                    'type': 'danger',
                }
            }

        # Création du service de vérification
        sync_service = self.env['insee.sync.service'].create({
            'siret': self.siret
        })
        
        # Vérification du SIRET
        result = sync_service.verify_siret()
        
        # Si on a un résultat
        if sync_service.has_result and sync_service.result_ids:
            result = sync_service.result_ids[0]
            # Mise à jour des données INSEE
            self.write({
                'insee_siren': self.siret[:9],
                'insee_enseigne': result.enseigne,
                'insee_tva': result.vat,
                'insee_activite_principale': result.activity_code,
                'last_insee_sync': fields.Datetime.now(),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _('Données INSEE mises à jour'),
                    'type': 'success',
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }
            
        return result  # Retourne l'erreur si pas de résultat

    @api.model
    def _cron_update_from_insee(self):
        """Méthode appelée par le cron pour mettre à jour les données INSEE"""
        # Recherche des partenaires à mettre à jour
        partners = self.search([
            ('is_company', '=', True),
            ('siret', '!=', False),
            '|',
            ('last_insee_sync', '=', False),
            ('last_insee_sync', '<', fields.Datetime.subtract(fields.Datetime.now(), days=30))
        ])

        for partner in partners:
            try:
                partner._verify_siret_from_insee()
                # Petit délai pour ne pas surcharger l'API INSEE
                time.sleep(1)
            except Exception as e:
                _logger.error(f"Erreur mise à jour INSEE pour {partner.name}: {str(e)}")
                continue