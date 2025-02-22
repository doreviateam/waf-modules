from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CalendarHoliday(models.Model):
    _inherit = 'calendar.holiday'
