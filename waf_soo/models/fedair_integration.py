from odoo import models, fields, api

class FedairZone(models.Model):
    _name = 'fedair.zone'
    _description = 'Zone d\'intervention FEDAIR'

    name = fields.Char('Nom de la zone', required=True)
    active = fields.Boolean('Actif', default=True)

class FedairGamme(models.Model):
    _name = 'fedair.gamme'
    _description = 'Gamme de produits FEDAIR'

    name = fields.Char('Nom de la gamme', required=True)
    description = fields.Text('Description')
    active = fields.Boolean('Actif', default=True)

class FedairDemandeDevis(models.Model):
    _name = 'fedair.demande.devis'
    _description = 'Demande de devis FEDAIR'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Référence', readonly=True, default='Nouveau')
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    date_demande = fields.Datetime('Date de demande', default=fields.Datetime.now)
    prenom = fields.Char('Prénom')
    nom = fields.Char('Nom')
    adresse = fields.Text('Adresse complète')
    email = fields.Char('Email')
    telephone = fields.Char('Téléphone')
    sujet = fields.Char('Sujet')
    message = fields.Text('Message')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('processed', 'Traité'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la création pour gérer la création en batch"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('fedair.demande.devis') or 'Nouveau'
        return super().create(vals_list)

    def write(self, vals):
        # Implementation of the write method
        super().write(vals)

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nouveau') == 'Nouveau':
            vals['name'] = self.env['ir.sequence'].next_by_code('fedair.demande.devis') or 'Nouveau'
        return super(FedairDemandeDevis, self).create(vals) 