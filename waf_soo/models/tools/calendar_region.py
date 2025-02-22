from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CalendarRegion(models.Model):
    _inherit = 'calendar.region'
