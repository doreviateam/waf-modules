from odoo import api, fields, models, _
from odoo.exceptions import UserError

class DispatchGroupWizard(models.TransientModel):
    _name = 'dispatch.group.wizard'
    _description = 'Assistant de regroupement des dispatches'

    scheduled_date = fields.Date(
        string='Date de livraison',
        required=True,
        default=fields.Date.today
    )
    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Adresse de livraison',
        required=True
    )
    dispatch_ids = fields.Many2many(
        'sale.line.dispatch',
        string='Dispatches à regrouper',
        domain="[('state', '=', 'confirmed'), ('picking_id', '=', False)]"
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Commande',
        required=True
    )
    delivery_addresses = fields.Many2many(
        'partner.address',
        string='Adresses disponibles',
        compute='_compute_delivery_addresses'
    )
    available_dispatch_ids = fields.Many2many(
        'sale.line.dispatch',
        string='Dispatches disponibles',
        compute='_compute_available_dispatches'
    )

    @api.depends('sale_order_id')
    def _compute_delivery_addresses(self):
        for wizard in self:
            wizard.delivery_addresses = self.env['partner.address'].search([
                ('partner_ids', 'in', [wizard.sale_order_id.partner_id.id]),
                ('type', '=', 'delivery'),
                ('active', '=', True)
            ])

    @api.depends('sale_order_id', 'scheduled_date', 'delivery_address_id')
    def _compute_available_dispatches(self):
        for wizard in self:
            domain = [
                ('sale_order_id', '=', wizard.sale_order_id.id),
                ('state', '=', 'confirmed'),
                ('picking_id', '=', False)
            ]
            if wizard.scheduled_date:
                domain.append(('scheduled_date', '=', wizard.scheduled_date))
            if wizard.delivery_address_id:
                domain.append(('delivery_address_id', '=', wizard.delivery_address_id.id))
            
            wizard.available_dispatch_ids = self.env['sale.line.dispatch'].search(domain)

    @api.onchange('sale_order_id', 'scheduled_date', 'delivery_address_id')
    def _onchange_filters(self):
        self.dispatch_ids = False
        return {'domain': {'dispatch_ids': [('id', 'in', self.available_dispatch_ids.ids)]}}

    def action_group_dispatches(self):
        if not self.dispatch_ids:
            raise UserError(_("Veuillez sélectionner au moins un dispatch à regrouper."))

        # Vérifier que tous les dispatches sont bien disponibles
        if not all(dispatch in self.available_dispatch_ids for dispatch in self.dispatch_ids):
            raise UserError(_("Certains dispatches sélectionnés ne sont plus disponibles pour le regroupement."))

        group = self.env['sale.dispatch.group'].create({
            'name': self.env['ir.sequence'].next_by_code('sale.dispatch.group'),
            'sale_order_id': self.sale_order_id.id,
            'delivery_address_id': self.delivery_address_id.id,
            'scheduled_date': self.scheduled_date,
            'state': 'confirmed'
        })

        self.dispatch_ids.write({'dispatch_group_id': group.id})
        
        # Créer le BL pour le groupe
        picking = group.action_create_picking()
        
        return {
            'name': _('Bon de livraison'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
        } 