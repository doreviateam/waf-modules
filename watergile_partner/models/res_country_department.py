from odoo import models, fields

class ResCountryDepartment(models.Model):
    _name = 'res.country.department'

    name = fields.Char(string='Département', required=True)
    code = fields.Char(string='Code', required=True)
    country_id = fields.Many2one('res.country', string='Pays', required=True)


class ResCountry(models.Model):
    _name = 'res.country'

    name = fields.Char(string='Pays', required=True)
    code = fields.Char(string='Code', required=True)

