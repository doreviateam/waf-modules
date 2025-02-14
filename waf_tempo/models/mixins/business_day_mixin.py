from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from workalendar.registry import registry
from datetime import date, timedelta

class BusinessDayMixin(models.AbstractModel):
    """
    Mixin pour la gestion des jours ouvrés avec prise des spécificités régionales
    """
    _name = 'business.day.mixin'
    _description = 'Mixin pour la gestion des jours ouvrés'
    _inherit = ['date.range.mixin']

    calendar_country = fields.Many2one(comodel_name='res.country', default=lambda self: self.env.ref('base.fr', False), required=True, 
                                       tracking=True, help="Pays pour lequel le calendrier est utilisé")
    calendar_region_id = fields.Many2one(
        comodel_name='calendar.region',
        compute='_compute_calendar_region_id', 
        store=True, 
        string="Région du calendrier", 
        help="Région du calendrier"
    )
    business_days_count = fields.Integer(compute='_compute_business_days', store=True, string="Nombre de jours ouvrés", help="Nombre de jours ouvrés dans la période")
    
    _calendar_instances = {}  # Cache pour les instances de calendrier

    def _get_calendar_key(self):
        """Génère une clé unique pour le cache du calendrier"""
        return f"{self.calendar_country.code}_{self.calendar_region_id.code or 'none'}"

    def _get_calendar_instance(self):
        """Récupération optimisée du calendrier avec cache"""
        self.ensure_one()
        cache_key = self._get_calendar_key()
        
        if cache_key not in self._calendar_instances:
            calendar = self._create_calendar_instance()
            self._calendar_instances[cache_key] = calendar
            
        return self._calendar_instances[cache_key]

    def _create_calendar_instance(self):
        """Création d'une nouvelle instance de calendrier"""
        country_code = self.calendar_country.code.lower()
        calendar_class = registry.get(country_code) or registry.get('france')
        calendar = calendar_class()
        
        if self.calendar_region_id:
            self._add_regional_holidays(calendar)
            
        return calendar

    def _add_regional_holidays(self, calendar):
        """Ajoute les jours fériés régionaux au calendrier"""
        if not self.calendar_region_id:
            return calendar

        original_holidays = calendar.holidays
        regional_holidays = self._get_regional_holidays()

        def extended_holidays(year):
            holidays = dict(original_holidays(year))
            for mmdd, name in regional_holidays.items():
                month, day = map(int, mmdd.split('-'))
                try:
                    holiday_date = date(year, month, day)
                    holidays[holiday_date] = name
                except ValueError:
                    continue
            return sorted(holidays.items())

        calendar.holidays = extended_holidays
        return calendar

    def _get_regional_holidays(self):
        """Retourne les jours fériés spécifiques à la région"""
        if not self.calendar_region_id:
            return {}

        return {
            'GP': {
                '05-27': "Abolition de l'esclavage (Guadeloupe)",
                '07-21': "Fête Victor Schœlcher",
            },
            'MQ': {
                '05-22': "Abolition de l'esclavage (Martinique)",
            },
            'GF': {
                '06-10': "Abolition de l'esclavage (Guyane)",
            },
            'RE': {
                '12-20': "Abolition de l'esclavage (Réunion)",
            },
        }.get(self.calendar_region_id.code, {})

    @api.depends('date_start', 'date_end', 'calendar_country', 'calendar_region_id')
    def _compute_business_days(self):
        for record in self:
            if not (record.date_start and record.date_end):
                record.business_days_count = 0
                continue

            try:
                calendar = record._get_calendar_instance()
                record.business_days_count = calendar.get_working_days_delta(
                    record.date_start,
                    record.date_end
                )
            except Exception:
                record.business_days_count = 0

    def is_business_day(self, check_date):
        """Vérifie si une date est un jour ouvré"""
        self.ensure_one()
        return self._get_calendar_instance().is_working_day(check_date)

    def get_business_days_info(self):
        """Retourne les informations détaillées sur les jours ouvrés"""
        self.ensure_one()
        calendar = self._get_calendar_instance()
        
        if not (self.date_start and self.date_end):
            return {}

        # Utilise la méthode du mixin parent
        period_info = self._get_period_info(self.date_start, self.date_end)
        
        # Récupération des jours fériés
        holidays = dict(calendar.holidays(self.date_start.year))
        if self.date_start.year != self.date_end.year:
            holidays.update(dict(calendar.holidays(self.date_end.year)))

        return {
            **period_info,
            'business_days': self.business_days_count,
            'holidays': {
                date_obj: name 
                for date_obj, name in holidays.items() 
                if self.date_start <= date_obj <= self.date_end
            },
            'region': self.calendar_region_id.name if self.calendar_region_id else None,
            'country': self.calendar_country.name,
        }

    def add_business_days(self, days_count):
        """Ajoute un nombre de jours ouvrés à la période"""
        self.ensure_one()
        if not self.date_end:
            self.date_end = self.date_start

        calendar = self._get_calendar_instance()
        self.date_end = calendar.add_working_days(self.date_end, days_count)
        return True

    @api.model
    def clear_calendar_cache(self):
        """Vide le cache des instances de calendrier"""
        self._calendar_instances.clear()

    @api.depends('calendar_country')
    def _compute_calendar_region_id(self):
        """Calcule la région du calendrier en fonction du pays"""
        for record in self:
            # Mapping des codes pays vers les régions spéciales
            special_regions = {
                'GP': 'Guadeloupe',
                'MQ': 'Martinique',
                'GF': 'Guyane',
                'RE': 'Réunion',
                'YT': 'Mayotte',
                'NC': 'Nouvelle-Calédonie',
                'PF': 'Polynésie française',
            }
            
            country_code = record.calendar_country.code
            if country_code in special_regions:
                region = self.env['calendar.region'].search([
                    ('country_id', '=', record.calendar_country.id),
                    ('code', '=', country_code)
                ], limit=1)
                
                if not region:
                    # Création automatique de la région si elle n'existe pas
                    region = self.env['calendar.region'].create({
                        'name': special_regions[country_code],
                        'code': country_code,
                        'country_id': record.calendar_country.id,
                    })
                
                record.calendar_region_id = region
            else:
                record.calendar_region_id = False
