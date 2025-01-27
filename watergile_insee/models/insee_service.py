from odoo import models, fields, api, _, tools
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

_logger = logging.getLogger(__name__)

class InseeAPIService(models.AbstractModel):
    _name = 'insee.api.service'
    _description = 'Service API INSEE'

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount('https://', HTTPAdapter(max_retries=self.retry_strategy))

    @api.model
    @tools.ormcache('siret')
    def _validate_siret(self, siret):
        cleaned = ''.join(filter(str.isdigit, siret or ''))
        if len(cleaned) != 14:
            return False, "Le SIRET doit contenir 14 chiffres"
        return self._compute_luhn(cleaned)

    def _compute_luhn(self, number):
        somme = sum(int(digit) * (1 if i % 2 else 2) for i, digit in enumerate(number))
        return somme % 10 == 0, "SIRET valide" if somme % 10 == 0 else "SIRET invalide"