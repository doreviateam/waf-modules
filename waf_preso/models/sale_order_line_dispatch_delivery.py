from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrderLineDispatchDelivery(models.Model):
    _name = 'sale.order.line.dispatch.delivery'
    _description = 'Livraison planifiée'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date, id'

    order_id = fields.Many2one(
        'sale.order',
        string='Commande',
        related='dispatch_id.order_id',
        store=True,
        index=True
    )

    dispatch_id = fields.Many2one(
        'sale.order.line.dispatch', 
        string='Dispatch',
        required=True,
        tracking=True
    )

    
    
    product_id = fields.Many2one(
        'product.product',
        related='dispatch_id.product_id',
        string='Produit',
        store=True,
        readonly=True
    )
    
    shipping_address_id = fields.Many2one(
        'res.partner',
        string='Adresse de livraison',
        required=True,
        tracking=True
    )
    
    scheduled_date = fields.Datetime(
        string='Date planifiée',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    quantity = fields.Float(
        string='Quantité',
        required=True,
        tracking=True
    )
    
    picking_id = fields.Many2one(
        'stock.picking',
        string='Bon de livraison',
        copy=False,
        tracking=True
    )
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('picking_created', 'BL Créé'),
        ('delivered', 'Livré'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', tracking=True)

    delivery_partner_id = fields.Many2one(
        'res.partner',
        related='dispatch_id.delivery_partner_id',
        string='Adhérent',
        store=True,
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.dispatch_id.message_post(
                body=_("Nouvelle livraison planifiée créée pour %s unités") % record.quantity
            )
        return records

    def action_create_picking(self):
        """Crée un bon de livraison pour cette livraison planifiée"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Vous ne pouvez créer un BL que pour une livraison en brouillon."))
        
        if not self.picking_id:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('warehouse_id.company_id', '=', self.env.company.id)
            ], limit=1)
            
            if not picking_type:
                raise UserError(_("Aucun type d'opération de sortie trouvé !"))
            
            vals = {
                'partner_id': self.shipping_address_id.id,
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'scheduled_date': self.scheduled_date,
                'origin': f"Dispatch {self.dispatch_id.display_name}",
            }
            
            picking = self.env['stock.picking'].create(vals)
            
            self.env['stock.move'].create({
                'name': self.dispatch_id.product_id.name,
                'product_id': self.dispatch_id.product_id.id,
                'product_uom_qty': self.quantity,
                'product_uom': self.dispatch_id.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
            })
            
            self.write({
                'picking_id': picking.id,
                'state': 'picking_created'
            })
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'view_mode': 'form',
                'view_type': 'form',
            } 