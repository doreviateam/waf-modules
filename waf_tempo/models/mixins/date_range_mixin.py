from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
from datetime import date, timedelta

class DateRangeMixin(models.AbstractModel):
    """
    Mixin pour la gestion des périodes de dates
    """
    _name = 'date.range.mixin'
    _description = 'Mixin pour la gestion des périodes de dates'
    _inherit = ['mail.thread']

    PERIOD_TYPES = [
        ('day', 'Jour'),
        ('week', 'Semaine'),
        ('month', 'Mois'),
        ('quarter', 'Trimestre'),
        ('year', 'Année'),
        ('custom', 'Personnalisé'),
    ]

    PERIOD_DURATIONS = {
        'day': relativedelta(days=1),
        'week': relativedelta(weeks=1),
        'month': relativedelta(months=1),
        'quarter': relativedelta(months=3),
        'year': relativedelta(years=1),
    }

    date_start = fields.Date(string='Date de début', required=True, default=fields.Date.context_today, tracking=True, index=True, help="Date de début de la période")
    date_end = fields.Date(string='Date de fin', tracking=True, index=True, help="Date de fin de la période")
    period_type = fields.Selection(PERIOD_TYPES,
                                   default='month',
                                   required=True,
                                   tracking=True,
                                   string="Type de période",
                                   help="Type de période (jour, semaine, mois, trimestre, année)")
    
    is_active_period = fields.Boolean(
        compute='_compute_is_active_period',
        search='_search_is_active_period',
        store=True,
        string="Période active",
        help="Indique si la période est active"
    )

    duration_days = fields.Integer(
        compute='_compute_duration_days',
        store=True,
        string="Durée en jours",
        help="Durée de la période en jours"
    )

    is_open_ended = fields.Boolean(
        compute='_compute_is_open_ended',
        store=True,
        string="Période ouverte",
        help="Indique si la période est ouverte"
    )

    @api.model
    def _get_period_info(self, start_date, end_date=None, period_type='month'):
        """Méthode utilitaire centralisée pour les calculs de période"""
        today = fields.Date.context_today(self)
        end = end_date or today
        
        return {
            'is_open_ended': not bool(end_date),
            'duration': (end - start_date).days + 1 if end >= start_date else 0,
            'is_active': start_date <= today and (not end_date or end >= today)
        }

    @api.depends('date_end')
    def _compute_is_open_ended(self):
        for record in self:
            record.is_open_ended = not bool(record.date_end)

    @api.depends('date_start', 'date_end')
    def _compute_duration_days(self):
        for record in self:
            if not record.date_start:
                record.duration_days = 0
            elif not record.date_end:
                record.duration_days = (fields.Date.context_today(self) - record.date_start).days + 1
            else:
                record.duration_days = (record.date_end - record.date_start).days + 1

    @api.depends('date_start', 'date_end')
    def _compute_is_active_period(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_active_period = (
                record.date_start <= today and 
                (not record.date_end or record.date_end >= today)
            )

    @api.model
    def _search_is_active_period(self, operator, value):
        """Permet la recherche sur is_active_period"""
        today = fields.Date.context_today(self)
        if operator not in ['=', '!=']:
            raise UserError(_("Opérateur de recherche non supporté pour is_active_period"))
        
        if operator == '=':
            operator = '!=' if not value else '='
            
        domain = ['&',
            ('date_start', '<=', today),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', today)
        ]
        
        return ['!'] + domain if operator == '!=' else domain

    def _validate_dates(self, start_date, end_date=None):
        """Validation centralisée des dates"""
        if end_date and start_date > end_date:
            raise ValidationError(_("La date de fin doit être postérieure à la date de début"))
        return True

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            record._validate_dates(record.date_start, record.date_end)

    def _get_period_duration(self, period_type=None):
        """Retourne la durée selon le type de période"""
        return self.PERIOD_DURATIONS.get(period_type or self.period_type)

    @api.onchange('period_type', 'date_start')
    def _onchange_period_type(self):
        """Ajuste automatiquement la date de fin selon le type de période"""
        if self.period_type and self.period_type != 'custom' and self.date_start:
            self.adjust_period()

    def adjust_period(self, period_type=None):
        """Ajuste la période selon le type"""
        self.ensure_one()
        if period_type == 'custom' or self.period_type == 'custom':
            return
            
        duration = self._get_period_duration(period_type)
        if not duration:
            raise UserError(_("Type de période non valide"))
            
        self.date_end = self.date_start + duration - relativedelta(days=1)

    def extend_period(self, duration=None, period_type=None):
        """Prolonge la période"""
        self.ensure_one()
        if not self.date_end:
            self.date_end = fields.Date.context_today(self)
            
        if duration:
            self.date_end = self.date_end + relativedelta(days=duration)
        elif period_type:
            duration = self._get_period_duration(period_type)
            if duration:
                self.date_end = self.date_end + duration

    def get_period_info(self):
        """Retourne les informations sur la période"""
        self.ensure_one()
        return {
            'start_date': self.date_start,
            'end_date': self.date_end,
            'period_type': self.period_type,
            'is_active': self.is_active_period,
            'duration': self.duration_days,
            'is_open_ended': self.is_open_ended,
        }