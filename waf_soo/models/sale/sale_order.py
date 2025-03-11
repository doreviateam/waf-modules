from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

# Constantes pour les modes de livraison
DELIVERY_MODE_STANDARD = 'standard'
DELIVERY_MODE_DISPATCH = 'dispatch'

# Constantes pour les états
STATE_DRAFT = 'draft'
STATE_SENT = 'sent'
STATE_SALE = 'sale'
STATE_DONE = 'done'
STATE_CANCEL = 'cancel'

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    """
    ce code doit fonctionner comme le code original de odoo 
    quand on clique sur confirmer et qu'on a sélectionné le mode de livraison "standard"
    mais le BL n'est pas généré. Je souhaite corriger cela.
    """

    delivery_mode = fields.Selection([
        (DELIVERY_MODE_STANDARD, 'Standard'),
        (DELIVERY_MODE_DISPATCH, 'Dispatch')
    ], string='Mode de livraison', 
       default=DELIVERY_MODE_STANDARD, 
       required=True, 
       tracking=True,
       help="Standard: Flux classique de livraison Odoo\n"
            "Dispatch: Mode de livraison avec répartition fine des quantités")
    
    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la méthode create pour initialiser le mode de livraison."""
        for vals in vals_list:
            if 'delivery_mode' not in vals:
                vals['delivery_mode'] = DELIVERY_MODE_STANDARD
        return super().create(vals_list)
    
    @api.onchange('delivery_mode')
    def _onchange_delivery_mode(self):
        """Gère le changement de mode de livraison."""
        self._validate_delivery_mode()

    def write(self, vals):
        """Surcharge de la méthode write pour gérer les modifications du mode de livraison."""
        if not self.ids or self.env.context.get('install_mode'):
            return super().write(vals)
            
        if 'delivery_mode' in vals:
            self._validate_delivery_mode()
            if vals['delivery_mode'] == DELIVERY_MODE_DISPATCH:
                super().write({'delivery_mode': DELIVERY_MODE_DISPATCH})
                for order in self.filtered(lambda o: o.state in [STATE_DRAFT, STATE_SENT]):
                    order._create_default_dispatches()
                return super().write({k: v for k, v in vals.items() if k != 'delivery_mode'})
            
        return super().write(vals)

    def unlink(self):
        """Surcharge de la méthode unlink pour gérer la suppression des commandes."""
        for order in self:
            if order.state not in [STATE_DRAFT, STATE_SENT, STATE_CANCEL]:
                raise UserError(_("Seules les commandes en brouillon, envoyées ou annulées peuvent être supprimées."))
            
            if order.delivery_mode == DELIVERY_MODE_DISPATCH:
                dispatches = self.env['sale.line.dispatch'].search([
                    ('sale_order_id', '=', order.id)
                ])
                if dispatches and any(dispatch.state != STATE_CANCEL for dispatch in dispatches):
                    raise UserError(_(
                        "Impossible de supprimer la commande : certains dispatches ne sont pas annulés. "
                        "Veuillez annuler tous les dispatches avant de supprimer la commande."
                    ))
                
                pickings = order.picking_ids
                if pickings and any(picking.state != STATE_CANCEL for picking in pickings):
                    raise UserError(_(
                        "Impossible de supprimer la commande : certains bons de livraison ne sont pas annulés. "
                        "Veuillez annuler tous les bons de livraison avant de supprimer la commande."
                    ))
        
        return super().unlink()

    def action_view_delivery(self):
        """Affiche la vue des bons de livraison avec un message adapté selon le mode."""
        self.ensure_one()
        pickings = self.picking_ids

        if not pickings:
            action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
            action['domain'] = [('id', 'in', [])]
            action['context'] = dict(self._context, default_partner_id=self.partner_id.id)
            if self.delivery_mode == DELIVERY_MODE_DISPATCH:
                action['help'] = """
                    <p class="o_view_nocontent_smiling_face">
                        Aucun bon de livraison n'a encore été créé.
                    </p>
                    <p>
                        Les bons de livraison seront créés automatiquement une fois les dispatches confirmés.
                    </p>
                """
            return action

        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        action['domain'] = [('id', 'in', pickings.ids)]
        if len(pickings) == 1:
            action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = pickings.id
        return action

    def _create_default_dispatches(self):
        self.ensure_one()
        if self.delivery_mode != DELIVERY_MODE_DISPATCH:
            raise UserError(_("Impossible de créer un dispatch : le mode de livraison doit être 'Dispatch'"))
            
        DispatchLine = self.env['sale.line.dispatch']
        
        for line in self.order_line.filtered(lambda l: l.product_id.dispatchable):
            existing_dispatch = DispatchLine.search([
                ('sale_order_line_id', '=', line.id),
                ('state', 'not in', ['cancel'])
            ])
            
            if not existing_dispatch:
                delivery_address_id = self.partner_shipping_id.default_delivery_address_id.id if hasattr(self.partner_shipping_id, 'default_delivery_address_id') else False
                
                if not delivery_address_id:
                    delivery_address = self.partner_shipping_id.address_ids.filtered(
                        lambda a: a.type == 'delivery' and a.active
                    )[:1]
                    delivery_address_id = delivery_address.id if delivery_address else False
                
                if not delivery_address_id:
                    raise UserError(_("Le partenaire %s n'a pas d'adresse de livraison configurée.", self.partner_shipping_id.name))

                DispatchLine.create({
                    'sale_order_id': self.id,
                    'sale_order_line_id': line.id,
                    'stakeholder_id': self.partner_shipping_id.id,
                    'delivery_address_id': delivery_address_id,
                    'quantity': line.product_uom_qty,
                    'planned_date': self.expected_date or fields.Date.today(),
                })

    def _log_order_lines(self):
        """Log les informations des lignes de commande pour le debugging."""
        _logger.info('--- Lignes de commande ---')
        for line in self.order_line:
            _logger.info('Ligne: %s - Quantité: %s', line.product_id.name, line.product_uom_qty)
            _logger.info('État de la ligne: %s', line.state)
            _logger.info('Mouvements de stock associés: %s', line.move_ids)

    def _validate_delivery_mode(self):
        """Valide le mode de livraison et ses contraintes."""
        if self.state not in [STATE_DRAFT, STATE_SENT]:
            raise UserError(_("Le mode de livraison ne peut être modifié que sur un devis non confirmé."))
            
        if self.delivery_mode == DELIVERY_MODE_DISPATCH:
            non_dispatchable_products = self.order_line.filtered(
                lambda l: not l.product_id.dispatchable
            ).mapped('product_id.display_name')
            
            if non_dispatchable_products:
                raise UserError(_(
                    "Les produits suivants ne peuvent pas être dispatchés :\n%s\n\n"
                    "Veuillez les retirer de la commande ou les configurer comme dispatchables.",
                    "\n".join(non_dispatchable_products)
                ))
            
            self.order_line.filtered(
                lambda l: l.product_id.dispatchable
            ).write({'dispatch_required': True})
        else:
            self.order_line.filtered(
                lambda l: not l.dispatch_ids
            ).write({'dispatch_required': False})

    def action_confirm(self):
        """Surcharge de la méthode de confirmation pour gérer la génération des BL selon le mode."""
        _logger.info('=== Début de action_confirm() ===')
        _logger.info('Commande de vente: %s', self.name)
        _logger.info('État actuel: %s', self.state)
        _logger.info('Mode de livraison: %s', self.delivery_mode)
        
        self._log_order_lines()
        
        if self.delivery_mode == DELIVERY_MODE_DISPATCH:
            _logger.info('Mode dispatch activé - Pas de génération automatique de BL')
            result = super(SaleOrder, self.with_context(
                no_picking=True, 
                no_stock_move=True
            )).action_confirm()
        else:
            _logger.info('Mode standard activé - Génération automatique de BL')
            result = super(SaleOrder, self).action_confirm()
        
        self._log_order_lines()
        
        _logger.info('--- Bons de livraison créés ---')
        for picking in self.picking_ids:
            _logger.info('Bon de livraison: %s', picking.name)
            _logger.info('État du BL: %s', picking.state)
            _logger.info('Type d\'opération: %s', picking.picking_type_id.name)
            for move in picking.move_ids:
                _logger.info('Mouvement: %s - Quantité: %s', move.product_id.name, move.product_uom_qty)
        
        _logger.info('État après confirmation: %s', self.state)
        _logger.info('=== Fin de action_confirm() ===')
        return result
