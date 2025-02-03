from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StateTransitionError(UserError):
    """Exception spécifique pour les erreurs de transition d'état"""
    pass

class StateTrackingMixin(models.AbstractModel):
    _name = 'waf.state.tracking'
    _inherit = 'mail.thread'
    _description = 'Mixin pour la gestion des états'

    STATE_MAPPING = {
        'draft': {
            'label': 'Brouillon',
            'sequence': 10,
            'next_states': ['confirmed', 'cancelled'],
            'active': True,
            'fold': False,
            'validation_required': False,
            'error_messages': {
                'invalid_source': _("Impossible de remettre en brouillon depuis l'état %s"),
            },
        },
        'confirmed': {
            'label': 'Confirmé',
            'sequence': 20,
            'next_states': ['done', 'cancelled'],
            'active': True,
            'fold': False,
            'validation_required': True,
            'error_messages': {
                'invalid_source': _("Impossible de confirmer depuis l'état %s"),
                'validation_error': _("Validation impossible : %s"),
            },
        },
        'done': {
            'label': 'Terminé',
            'sequence': 30,
            'next_states': [],
            'active': False,
            'fold': True,
            'validation_required': True,
            'error_messages': {
                'invalid_source': _("Impossible de terminer depuis l'état %s"),
                'validation_error': _("Impossible de terminer : %s"),
            },
        },
        'cancelled': {
            'label': 'Annulé',
            'sequence': 40,
            'next_states': ['draft'],
            'active': False,
            'fold': True,
            'validation_required': False,
            'error_messages': {
                'invalid_source': _("Impossible d'annuler depuis l'état %s"),
            },
        },
    }

    STATES = [(state, data['label']) for state, data in STATE_MAPPING.items()]

    state = fields.Selection(STATES, string='État', default='draft', required=True, tracking=True, index=True, help="État du document")
    active = fields.Boolean(string='Actif', default=True, compute='_compute_active', help="Active/désactive le suivi des états")

    def _get_state_data(self, state_code):
        """Retourne les données d'un état"""
        return self.STATE_MAPPING.get(state_code, {})

    def _get_next_states(self):
        """Retourne les états suivants possibles"""
        self.ensure_one()
        return self._get_state_data(self.state).get('next_states', [])

    def _check_transition_validity(self, new_state):
        """Vérifie la validité d'une transition"""
        self.ensure_one()
        current_state_data = self._get_state_data(self.state)
        new_state_data = self._get_state_data(new_state)

        if new_state not in current_state_data['next_states']:
            raise StateTransitionError(
                new_state_data['error_messages']['invalid_source'] % 
                current_state_data['label']
            )

        if new_state_data.get('validation_required'):
            validation_method = f'_validate_{new_state}'
            if hasattr(self, validation_method):
                validation_result = getattr(self, validation_method)()
                if validation_result is not True:
                    raise StateTransitionError(
                        new_state_data['error_messages']['validation_error'] % 
                        validation_result
                    )

        return True

    @api.depends('state')
    def _compute_active(self):
        """Calcule si le document est actif"""
        for record in self:
            record.active = self._get_state_data(record.state).get('active', True)

    def get_state_info(self):
        """Retourne toutes les informations sur l'état actuel"""
        self.ensure_one()
        current_state = self.state
        state_data = self._get_state_data(current_state)
        return {
            'current': current_state,
            'label': state_data['label'],
            'sequence': state_data['sequence'],
            'next_states': state_data['next_states'],
            'is_active': state_data['active'],
            'is_folded': state_data['fold'],
            'requires_validation': state_data['validation_required'],
        }
