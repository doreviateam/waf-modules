# /home/doreviateam/mes_projets/dorevia/waf_preso/wizards/create_dispatch_wizard.py

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class CreateDispatchWizard(models.TransientModel):
    _name = 'create.dispatch.wizard'
    _description = 'Assistant de création de dispatch'

    order_id = fields.Many2one('sale.order', string='Commande', required=True)
    sale_order_line_id = fields.Many2one(
        'sale.order.line', 
        string='Ligne de commande',
        domain="[('order_id', '=', order_id)]"
    )
    product_id = fields.Many2one(
        'product.product', 
        string='Produit', 
        related='sale_order_line_id.product_id'
    )
    delivery_partner_ids = fields.Many2many(
        'res.partner', 
        string='Points de livraison disponibles'
    )
    delivery_partner_id = fields.Many2one(
        'res.partner', 
        string='Adhérent',
        domain="[('id', 'in', delivery_partner_ids)]"
    )
    
    date_dispatch = fields.Datetime(
        'Date de dispatch', 
        default=fields.Datetime.now
    )
    dispatched_qty = fields.Float('Quantité à dispatcher')
    remaining_qty = fields.Float(
        'Quantité restante', 
        compute='_compute_remaining_qty'
    )
    delivery_planning_ids = fields.One2many(
        'create.dispatch.wizard.line',
        'wizard_id',
        string='Livraisons planifiées'
    )

    @api.depends('sale_order_line_id', 'dispatched_qty')
    def _compute_remaining_qty(self):
        for wizard in self:
            if wizard.sale_order_line_id:
                total_dispatched = sum(self.env['sale.order.line.dispatch'].search([
                    ('order_line_id', '=', wizard.sale_order_line_id.id)
                ]).mapped('dispatched_qty'))
                wizard.remaining_qty = wizard.sale_order_line_id.product_uom_qty - total_dispatched
            else:
                wizard.remaining_qty = 0.0

    @api.onchange('order_id')
    def _onchange_order_id(self):
        if self.order_id:
            self.delivery_partner_ids = self.order_id.delivery_partner_ids

    @api.constrains('dispatched_qty', 'sale_order_line_id')
    def _check_quantities(self):
        for wizard in self:
            if wizard.sale_order_line_id:
                total_dispatched = sum(self.env['sale.order.line.dispatch'].search([
                    ('order_line_id', '=', wizard.sale_order_line_id.id)
                ]).mapped('dispatched_qty'))
                remaining_qty = wizard.sale_order_line_id.product_uom_qty - total_dispatched
                
                if wizard.dispatched_qty > remaining_qty:
                    raise ValidationError(_(
                        "La quantité à dispatcher ne peut pas dépasser la quantité restante (%s)",
                        remaining_qty
                    ))

    def action_save_close(self):
        self.ensure_one()
        if self._create_dispatch():
            return {'type': 'ir.actions.act_window_close'}
        return False

    def action_save_create(self):
        self.ensure_one()
        if self._create_dispatch():
            action = self.env.ref('waf_preso.action_create_dispatch_wizard').read()[0]
            action['context'] = {'default_order_id': self.order_id.id}
            return action
        return False

    def _create_dispatch(self):
        self.ensure_one()
        vals = {
            'order_line_id': self.sale_order_line_id.id,
            'delivery_partner_id': self.delivery_partner_id.id,
            'quantity': self.dispatched_qty,
            'date_dispatch': self.date_dispatch,
        }
        dispatch = self.env['sale.order.line.dispatch'].create(vals)
        
        # Création des livraisons planifiées
        for line in self.delivery_planning_ids:
            self.env['sale.order.line.dispatch.delivery'].create({
                'dispatch_id': dispatch.id,
                'scheduled_date': line.scheduled_date,
                'shipping_address_id': line.shipping_address_id.id,
                'quantity': line.quantity,
            })
        
        return dispatch


class CreateDispatchWizardLine(models.TransientModel):
    _name = 'create.dispatch.wizard.line'
    _description = 'Ligne de planification de livraison'

    wizard_id = fields.Many2one(
        'create.dispatch.wizard',
        string='Wizard'
    )
    scheduled_date = fields.Datetime(
        string='Date planifiée',
        required=True
    )
    shipping_address_id = fields.Many2one(
        'res.partner',
        string='Adresse de livraison',
        # je veux que l'adresse de livraison soit l'adresse du point de livraison (celle de l'adhérent) par défaut 
        domain="[('parent_id', '=', delivery_partner_id)]",
        required=True
    )

    @api.onchange('wizard_id')
    def _onchange_wizard_id(self):
        for line in self:
            if line.wizard_id and line.wizard_id.delivery_partner_id:
                line.shipping_address_id = line.wizard_id.delivery_partner_id



    quantity = fields.Float(
        string='Quantité',
        required=True
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifié')
    ], string='État', default='draft')
