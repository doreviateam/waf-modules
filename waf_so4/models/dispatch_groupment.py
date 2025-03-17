from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from itertools import groupby
import logging

_logger = logging.getLogger(__name__)

class DispatchGroupment(models.Model):
    _inherit = 'sale.dispatch'

    def action_create_delivery(self):
        """Crée les bons de livraison groupés par date/stakeholder."""
        self.ensure_one()
        
        # 1. Récupérer les lignes confirmées
        lines = self.line_ids.filtered(lambda l: l.state == 'confirmed')
        if not lines:
            raise UserError(_("No confirmed lines to deliver."))

        # 2. Grouper les lignes par date ET stakeholder
        def groupby_key(line):
            return (line.scheduled_date, line.stakeholder_id.id)
        
        sorted_lines = lines.sorted(key=lambda l: (l.scheduled_date, l.stakeholder_id.id))
        grouped_lines = {}
        for key, group in groupby(sorted_lines, key=groupby_key):
            group_list = list(group)
            grouped_lines[key] = group_list

        # 3. Créer un BL par groupe
        pickings = self.env['stock.picking']
        for (scheduled_date, _stakeholder_id), group_lines in grouped_lines.items():
            picking_vals = self._prepare_picking_values(scheduled_date, group_lines)
            picking = self.env['stock.picking'].create(picking_vals)
            pickings |= picking
            
            # Marquer les lignes comme traitées
            for line in group_lines:
                line.write({
                    'picking_id': picking.id,
                    'state': 'done'
                })

        # 4. Lier les BL au dispatch
        self.write({'picking_ids': [(4, p.id) for p in pickings]})
        
        return True

    def _prepare_picking_values(self, scheduled_date, lines):
        """Prépare les valeurs pour la création du bon de livraison groupé."""
        self.ensure_one()
        
        picking_type = self.env.ref('stock.picking_type_out')
        location_id = picking_type.default_location_src_id
        location_dest_id = self.env.ref('stock.stock_location_customers')

        # Format: "SO00001 - DSP00001"
        origin = f"{self.sale_order_id.name} - {self.name}"

        moves = []
        for line in lines:
            moves.append((0, 0, {
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom.id,
                'location_id': location_id.id,
                'location_dest_id': location_dest_id.id,
                'sale_line_id': line.sale_order_line_id.id,
            }))

        return {
            'partner_id': line.stakeholder_id.id,
            'delivery_address_id': line.delivery_address_id.id,
            'mandator_id': self.mandator_id.id,
            
            # Nouveau format pour origin
            'origin': origin,
            
            'scheduled_date': scheduled_date,
            'company_id': self.env.company.id,
            'picking_type_id': picking_type.id,
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
            'state': 'draft',
            'move_ids': moves,
        }

    def action_done(self):
        """Surcharge pour créer les BL si nécessaire et marquer comme done."""
        for dispatch in self:
            if dispatch.state != 'confirmed':
                raise UserError(_("Only confirmed dispatches can be marked as done."))
            
            # Créer les BL s'il n'y en a pas
            if not dispatch.picking_ids:
                _logger.info(f"No delivery orders found for dispatch {dispatch.name}, creating them now...")
                dispatch.action_create_delivery()
            
            dispatch.write({'state': 'done'})
            
            _logger.info(f"Dispatch {dispatch.name} marked as done with pickings: {dispatch.picking_ids.mapped('name')}")

