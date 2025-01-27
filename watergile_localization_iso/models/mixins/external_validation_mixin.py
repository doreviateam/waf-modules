import sys
from datetime import datetime

if 'pytest' in sys.modules:
    # Pour les tests
    from unittest.mock import MagicMock
    
    class MockFields:
        Boolean = lambda *args, **kwargs: MagicMock()
        Datetime = lambda *args, **kwargs: MagicMock()
        Char = lambda *args, **kwargs: MagicMock()
        Text = lambda *args, **kwargs: MagicMock()
        
        @staticmethod
        def now():
            return datetime.now()
    
    class MockModels:
        class AbstractModel:
            def __init__(self, *args, **kwargs):
                self._name = 'external.validation.mixin'
                self._description = 'Mixin pour la validation externe'
            
            def ensure_one(self):
                pass
                
            def write(self, vals):
                return True
    
    models = MockModels()
    fields = MockFields()
    api = MagicMock()
    
    class ValidationError(Exception):
        pass
    
else:
    # Pour Odoo
    from odoo import models, fields, api
    from odoo.exceptions import ValidationError

class ExternalValidationMixin(models.AbstractModel):
    """Mixin pour la validation externe des données"""
    _name = 'external.validation.mixin'
    _description = 'Mixin pour la validation externe'

    validated = fields.Boolean(
        string='Validé',
        default=False,
        help='Indique si l\'enregistrement a été validé par un service externe'
    )
    
    validation_date = fields.Datetime(
        string='Date de validation',
        help='Date de la dernière validation externe'
    )
    
    validation_source = fields.Char(
        string='Source de validation',
        help='Service utilisé pour la validation'
    )
    
    validation_message = fields.Text(
        string='Message de validation',
        help='Message retourné par le service de validation'
    )

    def _set_validation_info(self, source: str, message: str = None):
        """Met à jour les informations de validation"""
        self.ensure_one()
        self.write({
            'validated': True,
            'validation_date': fields.Datetime.now(),
            'validation_source': source,
            'validation_message': message
        })

    def _reset_validation(self):
        """Réinitialise les informations de validation"""
        self.ensure_one()
        self.write({
            'validated': False,
            'validation_date': False,
            'validation_source': False,
            'validation_message': False
        })

    @api.model
    def validate_external(self):
        """
        Méthode à implémenter par les classes héritantes
        Returns:
            bool: True si la validation est réussie
        Raises:
            NotImplementedError: Si la méthode n'est pas implémentée
        """
        raise NotImplementedError(
            "La méthode validate_external doit être implémentée par la classe héritante"
        )

    def action_validate(self):
        """Action de validation appelable depuis l'interface"""
        self.ensure_one()
        try:
            if self.validate_external():
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Succès',
                        'message': 'Validation externe réussie',
                        'type': 'success',
                    }
                }
        except Exception as e:
            raise ValidationError(f"Erreur lors de la validation : {str(e)}")

    def action_reset_validation(self):
        """Action pour réinitialiser la validation"""
        self.ensure_one()
        self._reset_validation()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Information',
                'message': 'Validation réinitialisée',
                'type': 'info',
            }
        }