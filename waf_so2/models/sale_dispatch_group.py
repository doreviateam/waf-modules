from odoo import api, fields, models

class SaleDispatchGroup(models.Model):
    _name = 'sale.dispatch.group'
    _description = 'Groupe de Dispatch'
    _rec_name = 'name'

    name = fields.Char(string='Référence', readonly=True, copy=False)
    sale_order_id = fields.Many2one('sale.order', string='Commande', required=True)
    delivery_address_id = fields.Many2one('partner.address', string='Adresse de livraison', required=True)
    scheduled_date = fields.Date(string='Date prévue', required=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', required=True)
    dispatch_ids = fields.One2many('sale.line.dispatch', 'dispatch_group_id', string='Dispatches')
    picking_id = fields.Many2one('stock.picking', string='Bon de livraison')

    _sql_constraints = [
        ('unique_group_per_order_address_date', 
         'unique(sale_order_id, delivery_address_id, scheduled_date)',
         'Un groupe de dispatch existe déjà pour cette commande, adresse et date')
    ] 

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self._generate_group_name(vals)
        return super().create(vals_list)

    def _generate_group_name(self, vals):
        """Génère un nom unique pour le groupe de dispatch."""
        sale_order = self.env['sale.order'].browse(vals.get('sale_order_id'))
        address = self.env['partner.address'].browse(vals.get('delivery_address_id'))
        date = vals.get('scheduled_date')
        
        if isinstance(date, str):
            date = fields.Date.from_string(date)
            
        sequence = self.env['ir.sequence'].next_by_code('sale.dispatch.group') or '/'
        
        return f"GRP/{sale_order.name}/{address.name}/{date.strftime('%Y%m%d')}/{sequence}"

    def action_confirm(self):
        """Confirme le groupe et crée le picking associé."""
        for group in self:
            # Créer le picking
            picking = group.action_create_picking()
            if picking:
                group.write({
                    'picking_id': picking.id,
                    'state': 'confirmed'
                })
        return True

    def action_create_picking(self):
        """Crée le bon de livraison pour ce groupe de dispatch."""
        self.ensure_one()
        if not self.dispatch_ids:
            return False
            
        # Récupérer les informations de stock depuis la commande
        picking_type_id = self.sale_order_id.warehouse_id.out_type_id
        location_id = picking_type_id.default_location_src_id
        location_dest_id = self.sale_order_id.partner_id.property_stock_customer
            
        # Créer le picking
        picking_vals = {
            'partner_id': self.sale_order_id.partner_id.id,
            'picking_type_id': picking_type_id.id,
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
            'scheduled_date': self.scheduled_date,
            'origin': self.name,
            'dispatch_group_id': self.id,
        }
        
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Créer les mouvements de stock
        for dispatch in self.dispatch_ids:
            self.env['stock.move'].create({
                'name': dispatch.product_id.name,
                'product_id': dispatch.product_id.id,
                'product_uom_qty': dispatch.product_uom_qty,
                'product_uom': dispatch.product_uom.id,
                'picking_id': picking.id,
                'location_id': location_id.id,
                'location_dest_id': location_dest_id.id,
                'dispatch_id': dispatch.id,
            })
            
        return picking 