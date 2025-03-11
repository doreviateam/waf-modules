from odoo import models, fields, api, _

class PartnerBlaz(models.Model):
    _name = 'partner.blaz'
    _description = 'Partenaire Blaz'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nom', required=True, tracking=True)
    
    partner_ids = fields.One2many(
        'res.partner',
        'partner_blaz_id',
        string='Partenaires'
    )

    # name est le nom du partenaire Blaz est unique peu importe la casse
    _sql_constraints = [
        ('name_unique', 'unique (name)', 'Le nom du partenaire Blaz doit être unique')
    ]

    # on veut que le nom soit en majuscule
    def name_get(self):
        return [(partner.id, partner.name.upper()) for partner in self]

    # on veut que la longeur du nom soit de 10 caractères mais pas plus et pas moins 3 caractères
    @api.constrains('name')
    def _check_name_length(self):
        for partner in self:
            if len(partner.name) < 3 or len(partner.name) > 10:
                raise models.ValidationError('Le nom du partenaire Blaz doit être compris entre 3 et 10 caractères')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals:
                vals['name'] = vals['name'].upper()
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = vals['name'].upper()
        return super().write(vals)
