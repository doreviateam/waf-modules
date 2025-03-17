from odoo import models, fields, api

class ContactMessage(models.Model):
    _name = 'waf.contact.message'
    _description = 'Messages de contact'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nom', required=True)
    email = fields.Char(string='Email', required=True)
    subject = fields.Char(string='Sujet')
    message = fields.Text(string='Message', required=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    state = fields.Selection([
        ('new', 'Nouveau'),
        ('in_progress', 'En cours'),
        ('done', 'Traité')
    ], string='État', default='new', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Traitement des valeurs avant création
        for vals in vals_list:
            if not vals.get('subject'):
                vals['subject'] = 'Contact depuis le site web'
        return super().create(vals_list) 