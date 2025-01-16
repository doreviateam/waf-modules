from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    insee_consumer_key = fields.Char(string='Consumer Key', config_parameter='insee.consumer.key')
    insee_consumer_secret = fields.Char(string='Consumer Secret', config_parameter='insee.consumer.secret')
    insee_api_url = fields.Char(string='API URL', config_parameter='insee.api.url')
    insee_update_interval = fields.Integer(string='Intervalle de mise à jour (en jours)', config_parameter='insee.update.interval', 
                                           default=7)
    
    @api.onchange('insee_update_interval')
    def _onchange_insee_update_interval(self):
        if self.insee_update_interval < 1:
            self.insee_update_interval = 1
        elif self.insee_update_interval > 30:
            self.insee_update_interval = 30
    