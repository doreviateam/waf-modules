from odoo import fields, models, api

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_zone_id = fields.Many2one(
        'delivery.zone',
        string='Zone de livraison',
        tracking=True,
    )

    delivery_date = fields.Date(
        string='Date de livraison',
        tracking=True,
    )

    delivery_time_slot_id = fields.Many2one(
        'resource.calendar.attendance',
        string='Créneau horaire',
        tracking=True,
    )

    @api.onchange('delivery_zone_id')
    def _onchange_delivery_zone_id(self):
        if self.delivery_zone_id and self.picking_type_code == 'outgoing':
            return {'domain': {'carrier_id': [('id', 'in', self.delivery_zone_id.delivery_carrier_ids.ids)]}}
        return {'domain': {'carrier_id': []}} 