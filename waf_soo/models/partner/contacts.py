from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Contact(models.Model):
    _inherit = 'res.partner'