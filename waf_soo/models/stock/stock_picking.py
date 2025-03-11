from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Champs relationnels
    dispatch_id = fields.Many2one(
        'sale.line.dispatch',
        string='Dispatch associé',
        copy=False,
        readonly=True,
        index=True,
        ondelete='set null'
    )

    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Adresse de livraison',
        tracking=True,
        index=True,
        domain="[('partner_ids', 'in', partner_id)]"
    )

    # Champs d'adresse calculés et stockés
    delivery_address_name = fields.Char(
        string='Site de livraison',
        compute='_compute_delivery_address_fields',
        store=True,
        tracking=True
    )
    street = fields.Char(
        string='Rue',
        compute='_compute_delivery_address_fields',
        store=True,
        tracking=True
    )
    street2 = fields.Char(
        string='Rue 2',
        compute='_compute_delivery_address_fields',
        store=True,
        tracking=True
    )
    zip = fields.Char(
        string='Code postal',
        compute='_compute_delivery_address_fields',
        store=True,
        tracking=True
    )
    city = fields.Char(
        string='Ville',
        compute='_compute_delivery_address_fields',
        store=True,
        tracking=True
    )
    state_id = fields.Many2one(
        'res.country.state',
        string='Département',
        compute='_compute_delivery_address_fields',
        store=True,
        tracking=True
    )
    country_id = fields.Many2one(
        'res.country',
        string='Pays',
        compute='_compute_delivery_address_fields',
        store=True,
        tracking=True
    )

    @api.depends('delivery_address_id', 'delivery_address_id.name', 'delivery_address_id.street',
                'delivery_address_id.street2', 'delivery_address_id.zip', 'delivery_address_id.city',
                'delivery_address_id.state_id', 'delivery_address_id.country_id')
    def _compute_delivery_address_fields(self):
        for picking in self:
            if picking.delivery_address_id:
                picking.delivery_address_name = picking.delivery_address_id.name
                picking.street = picking.delivery_address_id.street
                picking.street2 = picking.delivery_address_id.street2
                picking.zip = picking.delivery_address_id.zip
                picking.city = picking.delivery_address_id.city
                picking.state_id = picking.delivery_address_id.state_id
                picking.country_id = picking.delivery_address_id.country_id
            else:
                picking.delivery_address_name = False
                picking.street = False
                picking.street2 = False
                picking.zip = False
                picking.city = False
                picking.state_id = False
                picking.country_id = False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id and not self.delivery_address_id:
            # Recherche de la première adresse de livraison du partenaire
            delivery_address = self.env['partner.address'].search([
                ('partner_ids', 'in', self.partner_id.id),
                ('type', '=', 'delivery')
            ], limit=1)
            if delivery_address:
                self.delivery_address_id = delivery_address.id

    # Surcharge de la méthode d'action de validation
    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if picking.dispatch_id and picking.state == 'done':
                if picking.dispatch_id.state != 'picking':
                    raise UserError(_("Le dispatch associé doit être en état 'En livraison' pour valider le bon de livraison."))
                picking.dispatch_id.action_done()
        return res

    # Surcharge de la méthode d'action d'annulation
    def action_cancel(self):
        res = super().action_cancel()
        for picking in self:
            if picking.dispatch_id and picking.state == 'cancel':
                picking.dispatch_id.action_cancel()
        return res

    # Méthode pour mettre à jour l'adresse depuis le dispatch
    def _update_address_from_dispatch(self, dispatch):
        self.ensure_one()
        if dispatch and dispatch.delivery_address_id:
            self.delivery_address_id = dispatch.delivery_address_id.id
