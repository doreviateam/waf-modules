from odoo import models, fields, api, _, tools
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

_logger = logging.getLogger(__name__)



class InseeSyncService(models.Model):
    _name = 'insee.sync.service'
    _description = 'Vérificateur SIRET'
    _inherit = ['insee.api.service']

    API_BASE_URL = 'https://api.insee.fr'
    API_TIMEOUT = 10

    siret = fields.Char(required=True)
    siret_valid = fields.Boolean(compute='_compute_siret_valid')
    siret_message = fields.Char(compute='_compute_siret_valid')
    result_ids = fields.One2many('insee.sync.result', 'sync_id')
    has_result = fields.Boolean(compute='_compute_has_result')

    @api.depends('result_ids')
    def _compute_has_result(self):
        for record in self:
            record.has_result = bool(record.result_ids)

    @api.model
    def _format_siret(self, siret):
        cleaned = ''.join(filter(str.isdigit, siret or ''))
        if len(cleaned) != 14:
            return False
        return f"{cleaned[:3]} {cleaned[3:6]} {cleaned[6:9]} {cleaned[9:]}"

    def verify_siret(self):
        self.ensure_one()
        try:
            data = self._fetch_insee_data()
            return self._create_sync_result(data)
        except Exception as e:
            _logger.error(f"Erreur INSEE: {str(e)}")
            return self._show_error(str(e))