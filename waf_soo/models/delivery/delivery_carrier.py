from odoo import models, fields, api

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    zone_ids = fields.Many2many(
        'delivery.zone',
        'delivery_zone_carrier_rel',  # Même nom de table que dans delivery.zone
        'carrier_id',                 # Inverse de zone_id
        'zone_id',                    # Inverse de carrier_id
        string='Zones de livraison',
        domain="[]",
        tracking=True,
        help="Zones de livraison couvertes par ce transporteur"
    )
    zone_count = fields.Integer(
        string='Nombre de zones',
        compute='_compute_zone_count'
    )

    @api.depends('zone_ids')
    def _compute_zone_count(self):
        for carrier in self:
            carrier.zone_count = len(carrier.zone_ids)

    def action_view_zones(self):
        self.ensure_one()
        return {
            'name': 'Zones de livraison',
            'type': 'ir.actions.act_window',
            'res_model': 'delivery.zone',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.zone_ids.ids)],
            'context': {'default_carrier_ids': [(6, 0, [self.id])]}
        }

    