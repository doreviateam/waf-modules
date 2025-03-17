from odoo import models, fields

class ContactMessage(models.Model):
    _name = 'waf.contact.message'
    _description = 'Messages du formulaire de contact'
    _order = 'create_date desc'

    name = fields.Char('Nom', required=True)
    email = fields.Char('Email', required=True)
    subject = fields.Char('Sujet', required=True)
    message = fields.Text('Message', required=True)
    create_date = fields.Datetime('Date', readonly=True)
    state = fields.Selection([
        ('new', 'Nouveau'),
        ('read', 'Lu'),
        ('replied', 'Répondu')
    ], string='État', default='new') 