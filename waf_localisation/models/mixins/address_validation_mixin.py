from odoo import models, api
import requests
from unidecode import unidecode
import re

class AddressValidationMixin(models.AbstractModel):
    _name = 'address.validation.mixin'
    _description = 'Mixin pour la validation des adresses'

    def _validate_french_address(self, street, street2, zip, city):
        """Valide une adresse française et retourne un score de qualité.
        
        Args:
            street (str): Rue
            street2 (str): Complément d'adresse
            zip (str): Code postal
            city (str): Ville
            
        Returns:
            dict: Résultat de la validation
        """
        # Score initial basé sur le format
        format_score = self._validate_address_format(street, zip, city)
        
        # Si le format est incorrect, on ne vérifie pas la BAN
        if format_score['score'] < 0.5:
            return format_score
            
        # Vérification BAN
        try:
            ban_score = self._check_ban_address(street, zip, city)
            # On combine les scores (format et existence)
            format_score['score'] *= ban_score
            format_score['details']['ban_valid'] = bool(ban_score > 0.8)
        except Exception:
            # En cas d'erreur de connexion, on garde juste le score de format
            format_score['details']['ban_valid'] = None
            
        return format_score

    def _validate_address_format(self, street, zip, city):
        """Validation du format des champs"""
        score = 1.0
        
        if not zip or not re.match(r'^\d{5}$', zip):
            score *= 0.7
            
        if not city:
            score *= 0.7
        else:
            city = unidecode(city.lower().strip())
            if not re.match(r'^[a-z\- ]+$', city):
                score *= 0.9
                
        if not street:
            score *= 0.7
        else:
            street = unidecode(street.lower().strip())
            if not re.search(r'\d+', street):
                score *= 0.9
            if not re.match(r'^[a-z0-9\- ]+$', street):
                score *= 0.9
                
        return {
            'score': score,
            'details': {
                'zip_valid': bool(zip and re.match(r'^\d{5}$', zip)),
                'city_valid': bool(city),
                'street_valid': bool(street),
            }
        }

    def _check_ban_address(self, street, zip, city):
        """Vérifie l'existence de l'adresse dans la BAN"""
        # TODO: Implémenter l'appel à l'API BAN
        # Pour l'instant, retourne 1.0 (validation OK)
        return 1.0

