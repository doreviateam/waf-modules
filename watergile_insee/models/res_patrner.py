from odoo import models, fields, api, _, tools
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    insee_siret = fields.Char(index=True, help="Numéro SIRET officiel")
    insee_siren = fields.Char(compute='_compute_siren', store=True, help="Numéro SIREN officiel")
    insee_enseigne = fields.Char(help="Enseigne")
    insee_tva = fields.Char(compute='_compute_tva', store=True, help="Numéro de TVA vérifié")
    insee_activite_principale = fields.Char(help="Activité principale")
    last_insee_sync = fields.Datetime(help="Date de la dernière synchronisation avec INSEE")

    @api.depends('insee_siret')
    def _compute_siren(self):
        for record in self:
            record.insee_siren = record.insee_siret and record.insee_siret[:9]

    @api.model
    def _cron_update_from_insee(self):
        partners = self._get_partners_to_update()
        for batch in tools.split_every(50, partners):
            self._process_batch_update(batch)
            self.env.cr.commit()