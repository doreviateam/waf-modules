"""
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StockMove(models.Model):
    _inherit = 'stock.move'

    # Relations Many2many
    groupment_ids = fields.Many2many(
        'partner.groupment',
        'stock_move_groupment_rel',
        'move_id',
        'groupment_id',
        related='dispatch_id.order_id.groupment_ids',
        string='Groupements',
        store=True,
        index=True,
        readonly=True
    )

    # Relations Many2one existantes
    dispatch_delivery_id = fields.Many2one(
        'sale.order.line.dispatch.delivery',
        string='Livraison dispatchée',
        index=True,
        ondelete='restrict',
        help="Livraison planifiée associée à ce mouvement"
    )

    dispatch_id = fields.Many2one(
        related='dispatch_delivery_id.dispatch_id',
        string='Dispatch',
        store=True,
        index=True,
        readonly=True
    )

    # Champs de traçabilité
    is_dispatch_move = fields.Boolean(
        string='Est un mouvement dispatché',
        compute='_compute_is_dispatch_move',
        store=True,
        help="Indique si le mouvement provient d'un dispatch"
    )

    dispatch_reference = fields.Char(
        string='Référence dispatch',
        compute='_compute_dispatch_reference',
        store=True,
        help="Référence unique pour le suivi"
    )

    dispatch_state = fields.Selection(
        related='dispatch_delivery_id.state',
        string='État du dispatch',
        store=True,
        index=True
    )

    delivery_zone_id = fields.Many2one(
        'delivery.zone',
        string='Zone de livraison',
        related='picking_id.delivery_zone_id',
        store=True,
        readonly=True,
    )

    picking_type_code = fields.Selection(
        related='picking_type_id.code',
        string='Type d\'opération',
        store=True,
    )

    # Calculs
    @api.depends('dispatch_delivery_id')
    def _compute_is_dispatch_move(self):
        for move in self:
            move.is_dispatch_move = bool(move.dispatch_delivery_id)

    @api.depends('dispatch_delivery_id', 'dispatch_id')
    def _compute_dispatch_reference(self):
        for move in self:
            if move.dispatch_delivery_id and move.dispatch_id:
                move.dispatch_reference = f"{move.dispatch_id.name}/{move.dispatch_delivery_id.name}"
            else:
                move.dispatch_reference = False

    # Contraintes
    @api.constrains('dispatch_delivery_id', 'state')
    def _check_dispatch_delivery_state(self):
        for move in self:
            if (move.dispatch_delivery_id and 
                move.state == 'done' and 
                move.dispatch_delivery_id.state != 'in_delivery'):
                raise ValidationError(_(
                    "Le mouvement ne peut pas être validé si la livraison "
                    "n'est pas en cours"
                ))

    # Surcharges
    def _get_new_picking_values(self):
        vals = super()._get_new_picking_values()
        if self.dispatch_delivery_id:
            vals.update({
                'dispatch_delivery_id': self.dispatch_delivery_id.id,
                'groupment_ids': self.groupment_ids.ids,
            })
        return vals

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        for move in self:
            if move.dispatch_delivery_id and move.state == 'done':
                move.dispatch_delivery_id._check_delivery_completion()
        return res

    def _action_cancel(self):
        res = super()._action_cancel()
        for move in self:
            if move.dispatch_delivery_id:
                move.dispatch_delivery_id._check_delivery_status()
        return res

    def _action_assign(self):
        res = super()._action_assign()
        for move in self:
            if move.dispatch_delivery_id:
                move.dispatch_delivery_id._update_availability()
        return res

    # Méthodes de traçabilité
    def get_dispatch_tracking_info(self):
        """Retourne les informations de traçabilité du dispatch"""
        self.ensure_one()
        if not self.dispatch_delivery_id:
            return {}
        
        return {
            'dispatch_ref': self.dispatch_reference,
            'delivery_ref': self.dispatch_delivery_id.name,
            'groupment': self.groupment_ids.name,
            'state': self.dispatch_state,
            'scheduled_date': self.dispatch_delivery_id.scheduled_date,
            'effective_date': self.dispatch_delivery_id.effective_date,
        }

