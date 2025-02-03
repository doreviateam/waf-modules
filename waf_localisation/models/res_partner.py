from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    address_validation_score = fields.Float(
        string='Score de validation (%)',
        compute='_compute_address_validation_score',
        store=True,
        default=0.0,
        help="Score de validation de l'adresse en pourcentage"
    )

    state_id = fields.Many2one(
        'res.country.state',
        string='Département',
        domain="[('country_id', '=', country_id)]"
    )

    @api.depends('street', 'street2', 'zip', 'city', 'country_id')
    def _compute_address_validation_score(self):
        validator = self.env['address.validation.mixin']
        for record in self:
            record.address_validation_score = 0.0

            if not record.country_id or record.country_id.code != 'FR':
                continue

            if not (record.street and record.zip and record.city):
                continue

            result = validator._validate_french_address(
                street=record.street or '',
                street2=record.street2 or '',
                zip=record.zip or '',
                city=record.city or ''
            )
            
            record.address_validation_score = result.get('score', 0.0)

    @api.onchange('country_id', 'zip', 'city', 'street', 'street2')
    def _onchange_address_validation(self):
        """Validation d'adresse en temps réel"""
        self._compute_address_validation_score()