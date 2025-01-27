from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PreSaleOrderLineDelivery(models.Model):
    _name = 'pre.sale.order.line.delivery'
    _description = 'Livraison planifiée'
    _order = 'delivery_date, delivery_time'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Champs relationnels
    sale_order_id = fields.Many2one('sale.order', related='preso_line_id.sale_order_id', store=True)
    preso_line_id = fields.Many2one('pre.sale.order.line', required=True, ondelete='cascade')

    is_preso = fields.Boolean(string='Is Preso', related='preso_line_id.is_preso', store=True)
    confirm_dispatch = fields.Boolean(string='Confirm Dispatch', default=False)

    product_id = fields.Many2one(related='preso_line_id.product_id', store=True, readonly=True)
    partner_id = fields.Many2one(related='preso_line_id.partner_id', store=True, readonly=True)
    
    # Champs de livraison
    delivery_address_id = fields.Many2one('res.partner', required=True, tracking=True)
    delivery_date = fields.Date(required=True, tracking=True)
    delivery_time = fields.Float(tracking=True)
    picking_id = fields.Many2one('stock.picking', tracking=True)
    
    # Champs quantités et prix
    quantity = fields.Float(required=True, digits='Product Unit of Measure', tracking=True)
    unit_price = fields.Float(related='preso_line_id.unit_price', store=True, readonly=True)
    uom_id = fields.Many2one(related='product_id.uom_id', store=True, readonly=True)
    
    # Champs techniques
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('done', 'Livré'),
        ('cancel', 'Annulé')
    ], default='draft', required=True, tracking=True)

    sale_order_line_id = fields.Many2one('sale.order.line',
        string='Ligne de commande',
        ondelete='cascade')

    _sql_constraints = [
        ('check_quantity_positive', 'CHECK(quantity > 0)', 'La quantité doit être positive'),
        ('check_delivery_time', 'CHECK(delivery_time >= 0 AND delivery_time < 24)', 'L\'heure doit être entre 0 et 24')
    ]

    @api.constrains('quantity')
    def _check_quantity(self):
        for delivery in self:
            # Calculer le total déjà planifié pour cette ligne
            total_planned = sum(
                d.quantity for d in delivery.preso_line_id.delivery_ids.filtered(
                    lambda d: d.state != 'cancel' and d.id != delivery.id
                )
            )
            
            # Vérifier que le total ne dépasse pas la quantité du dispatch
            if total_planned + delivery.quantity > delivery.preso_line_id.quantity:
                raise ValidationError(_(
                    "La quantité totale planifiée (%s) ne peut pas dépasser "
                    "la quantité du dispatch (%s)"
                ) % (total_planned + delivery.quantity, delivery.preso_line_id.quantity))

    @api.onchange('preso_line_id')
    def _onchange_preso_line(self):
        if self.preso_line_id:
            self.delivery_address_id = self.preso_line_id.delivery_address_id

    def action_confirm(self):
        for delivery in self:
            if delivery.state == 'draft':
                delivery.state = 'confirmed'

    def action_done(self):
        for delivery in self:
            if delivery.state == 'confirmed':
                delivery.state = 'done'

    def action_cancel(self):
        for delivery in self:
            if delivery.state in ['draft', 'confirmed']:
                delivery.state = 'cancel'

    def action_reset_to_draft(self):
        for delivery in self:
            if delivery.state == 'cancel':
                delivery.state = 'draft'
