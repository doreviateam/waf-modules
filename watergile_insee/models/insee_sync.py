from odoo import models, fields, api, _
import requests
import logging

_logger = logging.getLogger(__name__)

class InseeSyncService(models.Model):
    _name = 'insee.sync.service'
    _description = 'Vérificateur SIRET'

    # Configuration API INSEE
    API_BASE_URL = 'https://api.insee.fr'
    API_TIMEOUT = 10

    # Champs de base
    siret = fields.Char(
        string='SIRET',
        required=True,
        help="Numéro SIRET à vérifier"
    )
    siret_valid = fields.Boolean(
        string='SIRET Valide',
        compute='_compute_siret_valid',
        store=False
    )
    siret_message = fields.Char(
        string='Message',
        compute='_compute_siret_valid',
        store=False
    )

    # Champs résultat
    result_ids = fields.One2many(
        'insee.sync.result',
        'sync_id',
        string="Résultats"
    )

    has_result = fields.Boolean(
        compute='_compute_has_result',
        store=False
    )

    @api.depends('result_ids')
    def _compute_has_result(self):
        for record in self:
            record.has_result = bool(record.result_ids)

    @api.depends('siret')
    def _compute_siret_valid(self):
        for record in self:
            if not record.siret:
                record.siret_valid = False
                record.siret_message = "Veuillez saisir un SIRET"
                continue

            # Nettoyage
            cleaned = ''.join(filter(str.isdigit, record.siret))
            
            # Vérification longueur
            if len(cleaned) != 14:
                record.siret_valid = False
                record.siret_message = "Le SIRET doit contenir 14 chiffres"
                continue

            # Vérification Luhn
            somme = 0
            for i, digit in enumerate(cleaned):
                digit = int(digit)
                if i % 2 == 0:
                    doubled = digit * 2
                    somme += doubled if doubled < 10 else doubled - 9
                else:
                    somme += digit

            record.siret_valid = (somme % 10 == 0)
            record.siret_message = "SIRET valide" if record.siret_valid else "SIRET invalide"

    @api.onchange('siret')
    def _onchange_siret(self):
        """Auto-format du SIRET pendant la saisie"""
        if self.siret:
            # Garde uniquement les chiffres
            cleaned = ''.join(filter(str.isdigit, self.siret))
            
            if len(cleaned) <= 14:
                # Format: XXX XXX XXX XXXXX
                formatted = ''
                for i, char in enumerate(cleaned):
                    if i in [3, 6, 9]:  # Positions des espaces
                        formatted += ' '
                    formatted += char
                
                self.siret = formatted.strip()

    def _get_insee_token(self):
        """Récupère le token INSEE"""
        params = self.env['ir.config_parameter'].sudo()
        key = params.get_param('insee.consumer.key')
        secret = params.get_param('insee.consumer.secret')
        
        if not (key and secret):
            raise ValueError("Clés API INSEE non configurées")
            
        response = requests.post(
            f"{self.API_BASE_URL}/token",
            auth=(key, secret),
            data={'grant_type': 'client_credentials'},
            timeout=self.API_TIMEOUT
        )
        response.raise_for_status()
        return response.json()['access_token']

    def verify_siret(self):
        """Vérifie et récupère les informations du SIRET"""
        self.ensure_one()
        
        # Nettoyage et vérification basique
        siret = ''.join(filter(str.isdigit, self.siret or ''))
        if len(siret) != 14:
            return self._show_error('Le SIRET doit contenir 14 chiffres')
        
        # Vérification Luhn
        somme = 0
        for i, digit in enumerate(siret):
            digit = int(digit)
            if i % 2 == 0:
                doubled = digit * 2
                somme += doubled if doubled < 10 else doubled - 9
            else:
                somme += digit
        
        if somme % 10 != 0:
            return self._show_error('SIRET invalide (clé de contrôle)')
            
        # Récupération données INSEE
        try:
            token = self._get_insee_token()
            response = requests.get(
                f"{self.API_BASE_URL}/entreprises/sirene/V3.11/siret/{siret}",
                headers={'Authorization': f'Bearer {token}'},
                timeout=self.API_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            # Extraction des données
            etablissement = data.get('etablissement', {})
            unite_legale = etablissement.get('uniteLegale', {})
            adresse = etablissement.get('adresseEtablissement', {})
            
            # Formatage de l'adresse
            formatted_address = self._format_address(adresse)
            
            # Création du résultat
            self.env['insee.sync.result'].create({
                'sync_id': self.id,
                'company_name': unite_legale.get('denominationUniteLegale'),
                'enseigne': unite_legale.get('denominationUsuelleUniteLegale'),
                'activity_code': unite_legale.get('activitePrincipaleUniteLegale'),
                'address': formatted_address['address'],
                'zip_code': formatted_address['zip_code'],
                'city': formatted_address['city']
            })
            
            # Retourne l'action avec le titre personnalisé
            return {
                'type': 'ir.actions.act_window',
                'name': 'Doreviateam - Vérification SIRET',
                'res_model': 'insee.sync.service',
                'res_id': self.id,
                'view_mode': 'form',
                'view_id': self.env.ref('watergile_insee.view_insee_verify_form').id,
                'target': 'new',
                'flags': {'mode': 'readonly'}
            }
            
        except Exception as e:
            _logger.error(f"Erreur INSEE: {str(e)}")
            return self._show_error(f"Erreur de récupération: {str(e)}")

    def _format_address(self, address_data):
        """Formate l'adresse depuis les données INSEE"""
        street_elements = [
            address_data.get('numeroVoieEtablissement', ''),
            address_data.get('typeVoieEtablissement', ''),
            address_data.get('libelleVoieEtablissement', '')
        ]
        return {
            'address': ' '.join(filter(None, street_elements)),
            'zip_code': address_data.get('codePostalEtablissement'),
            'city': address_data.get('libelleCommuneEtablissement')
        }

    def _show_error(self, message):
        """Affiche un message d'erreur"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Erreur'),
                'message': _(message),
                'type': 'danger',
                'sticky': True
            }
        }

class InseeSyncResult(models.Model):
    _name = 'insee.sync.result'
    _description = 'Résultat vérification SIRET'
    _transient = True

    sync_id = fields.Many2one('insee.sync.service', string='Vérification')
    company_name = fields.Char('Raison sociale')
    enseigne = fields.Char('Enseigne commerciale')
    vat = fields.Char('N° TVA', compute='_compute_vat', store=False)
    activity_code = fields.Char('Code NAF')
    address = fields.Text('Adresse')
    zip_code = fields.Char('Code postal')
    city = fields.Char('Ville')

    @api.depends('sync_id.siret')
    def _compute_vat(self):
        """Calcule le numéro de TVA à partir du SIRET"""
        for record in self:
            if record.sync_id.siret:
                siret = ''.join(filter(str.isdigit, record.sync_id.siret))
                if len(siret) == 14:
                    siren = siret[:9]
                    key = (12 + 3 * (int(siren) % 97)) % 97
                    record.vat = f"FR{key:02d}{siren}"
                else:
                    record.vat = False
            else:
                record.vat = False