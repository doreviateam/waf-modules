from odoo import api, fields, models, _

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    dispatch_line_ids = fields.One2many(
        'sale.order.line.dispatch',
        'order_line_id',
        string='Lignes de dispatch'
    )
    dispatched_qty = fields.Float(
        string='Quantité dispatchée', 
        compute='_compute_dispatched_qty',
        help="Quantité dispatchée"
    )
    remaining_qty = fields.Float(
        string='Quantité restante', 
        compute='_compute_remaining_qty',
        help="Quantité restante"
    )
    dispatch_state = fields.Selection(string='État du dispatch', 
                                      selection=[('draft', "Non dispatché"),
                                                 ('partial', "En cours"),
                                                 ('done', "Terminé")],
                                      default='draft',
                                      help="État du dispatch")
    
    @api.depends('dispatch_line_ids')
    def _compute_dispatched_qty(self):
        for line in self:
            line.dispatched_qty = sum(line.dispatch_line_ids.mapped('quantity'))

    @api.depends('product_uom_qty', 'dispatched_qty')
    def _compute_remaining_qty(self):
        for line in self:
            line.remaining_qty = line.product_uom_qty - line.dispatched_qty

    @api.model
    def _prepare_dispatching_line(self):
        self.ensure_one()
        return {
            'sale_order_line_id': self.id,
            'product_id': self.product_id.id
        }

    @api.depends('order_id.delivery_partner_ids', 'order_id.agent_id')
    def _compute_delivery_partner_ids(self):
        for line in self:
            if line.order_id.agent_id:
                line.delivery_partner_ids = line.order_id.delivery_partner_ids
            else:
                line.delivery_partner_ids = self.env['res.partner'].search([])

    delivery_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_delivery_partner_ids',
        store=True,
        string='Points de livraison autorisés'
    )
