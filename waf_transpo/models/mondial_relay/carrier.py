from odoo import models, fields, api, _

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    def _compute_can_generate_return(self):
        """Surcharge pour activer les retours Mondial Relay"""
        super()._compute_can_generate_return()
        for carrier in self:
            if carrier.delivery_type == 'mondialrelay':
                carrier.can_generate_return = True

    @api.onchange('delivery_type')
    def _onchange_delivery_type(self):
        if self.delivery_type == 'mondial_relay':
            # Configuration spécifique pour Mondial Relay
            self.integration_level = 2
            self.mondial_relay_merchant = ''  # Valeur par défaut
            self.mondial_relay_key = ''       # Valeur par défaut
        else:
            # Ne pas appeler super() car la méthode n'existe pas dans la classe parente
            return {} 