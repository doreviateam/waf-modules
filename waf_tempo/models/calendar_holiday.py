from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from workalendar.europe import France
from datetime import datetime
from dateutil.easter import easter

class AlsaceMoselleCalendar(France):
    """Calendrier spécifique pour l'Alsace-Moselle"""
    include_good_friday = True
    include_boxing_day = True

class CalendarHoliday(models.Model):
    _name = 'calendar.holiday'
    _description = 'Jour férié spécifique'
    _order = 'date'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nom', required=True, tracking=True, translate=True, help="Nom du jour férié")
    date = fields.Date(string='Date', required=True, tracking=True, help="Date du jour férié")
    region_id = fields.Many2one(comodel_name='calendar.region', string='Région', required=True, tracking=True, ondelete='cascade', help="Région concernée par ce jour férié")
    type = fields.Selection([('fixed', 'Date fixe'), ('variable', 'Date variable')], string='Type', required=True, default='fixed', tracking=True, help="Type de jour férié (fixe ou variable)")
    variable_type = fields.Selection([
        ('easter', 'Pâques'),
        ('good_friday', 'Vendredi Saint'),
        ('easter_monday', 'Lundi de Pâques'),
        ('ascension', 'Ascension'),
        ('pentecost', 'Pentecôte'),
        ('pentecost_monday', 'Lundi de Pentecôte'),
        ('assumption', 'Assomption'),
        ('all_saints', 'Toussaint'),
        ('armistice', 'Armistice'),
        ('christmas', 'Noël'),
        ('new_year', 'Jour de l\'An'),
        ('labor_day', 'Fête du Travail'),
        ('victory_1945', 'Victoire 1945'),
        ('bastille', 'Fête Nationale'),
        ('abolition', 'Abolition de l\'esclavage'),
    ], string='Type de date variable')
    month = fields.Integer(string='Mois', tracking=True, help="Mois du jour férié (pour les dates fixes)")  
    day = fields.Integer(string='Jour', tracking=True, help="Jour du mois (pour les dates fixes)")
    weekday = fields.Selection([
        ('0', 'Lundi'),
        ('1', 'Mardi'),
        ('2', 'Mercredi'),
        ('3', 'Jeudi'),
        ('4', 'Vendredi'),
        ('5', 'Samedi'),
        ('6', 'Dimanche')
    ], string='Jour de la semaine', compute='_compute_weekday', store=True)
    description = fields.Text(string='Description', translate=True, help="Description détaillée du jour férié")
    active = fields.Boolean(default=True, tracking=True, help="Indique si le jour férié est actif")
    display_name = fields.Char(string='Nom affiché', compute='_compute_display_name', help="Nom affiché du jour férié")

    @api.constrains('month', 'day')
    def _check_date(self):
        for record in self:
            if record.type == 'fixed':
                if not (1 <= record.month <= 12):
                    raise ValidationError(_("Le mois doit être compris entre 1 et 12"))
                try:
                    date(2000, record.month, record.day)
                except ValueError:
                    raise ValidationError(_("Date invalide"))

    @api.onchange('type', 'month', 'day')
    def _onchange_date_components(self):
        if self.type == 'fixed' and self.month and self.day:
            try:
                self.date = date(fields.Date.today().year, self.month, self.day)
            except ValueError:
                pass

    @api.depends('name', 'date', 'region_id.name')
    def _compute_display_name(self):
        for record in self:
            name = record.name
            if record.date:
                name = f"{name} ({record.date})"
            if record.region_id:
                name = f"{name} - {record.region_id.name}"
            record.display_name = name

    @api.depends('date')
    def _compute_weekday(self):
        """Calcule le jour de la semaine à partir de la date"""
        for holiday in self:
            if holiday.date:
                holiday.weekday = str(holiday.date.weekday())
            else:
                holiday.weekday = False

    def _compute_variable_date(self, year):
        """Calcule la date en fonction du type de date variable"""
        self.ensure_one()
        if not self.variable_type:
            return False

        easter_date = easter(year)

        date_mapping = {
            'easter': easter_date,
            'good_friday': easter_date - timedelta(days=2),
            'easter_monday': easter_date + timedelta(days=1),
            'ascension': easter_date + timedelta(days=39),
            'pentecost': easter_date + timedelta(days=49),
            'pentecost_monday': easter_date + timedelta(days=50),
            'assumption': datetime(year, 8, 15),
            'all_saints': datetime(year, 11, 1),
            'armistice': datetime(year, 11, 11),
            'christmas': datetime(year, 12, 25),
            'new_year': datetime(year, 1, 1),
            'labor_day': datetime(year, 5, 1),
            'victory_1945': datetime(year, 5, 8),
            'bastille': datetime(year, 7, 14),
        }

        # Dates spécifiques par région pour l'abolition de l'esclavage
        abolition_dates = {
            'GP': (5, 27),  # Guadeloupe
            'MQ': (5, 22),  # Martinique
            'GF': (6, 10),  # Guyane
            'RE': (12, 20), # Réunion
            'YT': (4, 27),  # Mayotte
        }

        if self.variable_type == 'abolition' and self.region_id.code in abolition_dates:
            month, day = abolition_dates[self.region_id.code]
            return datetime(year, month, day)

        return date_mapping.get(self.variable_type, False)

    def action_compute_dates(self):
        """Action appelée depuis le bouton dans l'interface"""
        year = self.env.context.get('year', fields.Date.today().year)
        self.compute_variable_dates(year)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Succès',
                'message': f'Les dates variables pour {year} ont été mises à jour',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def compute_variable_dates(self, year=None):
        """Calcule les dates variables pour une année donnée"""
        if not year:
            year = fields.Date.today().year

        # Dictionnaire des calendriers par région
        calendars = {
            'GP': France(),  # Guadeloupe
            'MQ': France(),  # Martinique
            'GF': France(),  # Guyane
            'RE': France(),  # Réunion
            'YT': France(),  # Mayotte
            '67': AlsaceMoselleCalendar(),  # Bas-Rhin
            '68': AlsaceMoselleCalendar(),  # Haut-Rhin
            '57': AlsaceMoselleCalendar(),  # Moselle
            'FR': France(),  # France métropolitaine (par défaut)
        }

        # Pour chaque région, on calcule ses jours fériés
        for holiday in self.search([('type', '=', 'variable')]):
            region_code = holiday.region_id.code
            calendar = calendars.get(region_code, calendars['FR'])
            
            # Récupère les jours fériés pour cette région
            holidays = calendar.holidays(year)
            
            # Cherche la correspondance par nom
            for date, name in holidays:
                if name.lower() in holiday.name.lower():
                    holiday.write({
                        'date': date,
                        'month': date.month,
                        'day': date.day
                    })
                    break

        return True