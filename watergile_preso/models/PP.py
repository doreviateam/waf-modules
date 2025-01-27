from odoo import models, fields, api


class PreSaleOrderMovements(models.Model):
    _name = 'pre.sale.order.movements'
    _description = 'Mouvements de préparation de commande'
    _order = 'create_date DESC'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    sale_order_id = fields.Many2one('sale.order', required=True, index=True)
    product_id = fields.Many2one('product.product', required=True, index=True)
    pre_sale_order_line_id = fields.Many2one('pre.sale.order.line')
    
    description = fields.Char(required=True)
    debit = fields.Float(default=0.0)
    credit = fields.Float(default=0.0)
    running_balance = fields.Float(compute='_compute_running_balance', store=True)
    
    company_id = fields.Many2one(
        'res.company', 
        required=True, 
        default=lambda self: self.env.company
    )

    _sql_constraints = [
        ('check_movement_values', 
         'CHECK(debit >= 0 AND credit >= 0)', 
         'Les valeurs doivent être positives')
    ]

    @api.depends('sale_order_id', 'product_id', 'create_date')
    def _compute_running_balance(self):
        for record in self:
            previous_movements = self.search([
                ('sale_order_id', '=', record.sale_order_id.id),
                ('product_id', '=', record.product_id.id),
                ('create_date', '<=', record.create_date)
            ], order='create_date')
            
            balance = 0
            for movement in previous_movements:
                balance += movement.debit - movement.credit
            record.running_balance = balance

class PreSaleOrderLine(models.Model):
    _name = 'pre.sale.order.line'
    _description = 'Ligne de préparation de commande'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'delivery_date'

    sale_order_id = fields.Many2one('sale.order', required=True, index=True)
    sale_order_line_id = fields.Many2one(
        'sale.order.line', 
        ondelete='cascade',
        index=True
    )
    product_id = fields.Many2one(
        'product.product',
        required=True,
        tracking=True,
        index=True
    )
    
    quantity = fields.Float(
        required=True,
        digits='Product Unit of Measure',
        tracking=True
    )
    quantity_delivered = fields.Float(
        compute='_compute_quantities',
        store=True
    )
    quantity_remaining = fields.Float(
        compute='_compute_quantities',
        store=True
    )
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('cancelled', 'Annulé')
    ], default='draft', required=True, tracking=True)

    @api.depends('delivery_ids.state', 'delivery_ids.quantity')
    def _compute_quantities(self):
        for line in self:
            delivered = sum(
                d.quantity for d in line.delivery_ids.filtered(
                    lambda d: d.state == 'done'
                )
            )
            line.quantity_delivered = delivered
            line.quantity_remaining = line.quantity - delivered

    @api.model
    def create(self, vals):
        record = super().create(vals)
        record._create_movement(record.quantity)
        return record

    def _create_movement(self, quantity):
        if quantity <= 0:
            return
            
        self.env['pre.sale.order.movements'].create({
            'sale_order_id': self.sale_order_id.id,
            'product_id': self.product_id.id,
            'pre_sale_order_line_id': self.id,
            'credit': quantity,
            'description': f"Dispatch - {self.product_id.name}"
        })