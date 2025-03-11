from odoo import api, fields, models, _
from odoo.exceptions import UserError
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

    delivery_mode = fields.Selection([
        (DELIVERY_MODE_STANDARD, 'Standard'),
        (DELIVERY_MODE_DISPATCH, 'Dispatch')
    ], string='Mode de livraison', 
       default=DELIVERY_MODE_STANDARD, 
       required=True, 
       tracking=True,
       help="Standard: Flux classique de livraison Odoo\n"
            "Dispatch: Mode de livraison avec répartition fine des quantités")

    @api.onchange('delivery_mode')
    def _onchange_delivery_mode(self):
        """Gère le changement de mode de livraison."""
        if self.state not in ['draft', 'sent']:
            raise UserError(_("Le mode de livraison ne peut être modifié que sur un devis non confirmé."))

    def _log_order_lines(self):
        """Log les informations des lignes de commande pour le debugging."""
        _logger.info('--- Lignes de commande ---')
        for line in self.order_line:
            _logger.info('Ligne: %s - Quantité: %s', line.product_id.name, line.product_uom_qty)
            _logger.info('État de la ligne: %s', line.state)
            _logger.info('Mouvements de stock associés: %s', line.move_ids)

    def _validate_dispatch_mode(self):
        """Vérifie que le mode dispatch peut être utilisé."""
        if not self.partner_id.child_ids:
            raise UserError(_("Le mode dispatch nécessite des adresses de livraison associées au client."))
        
        # Vérifier que les quantités sont divisibles par le nombre d'adresses
        for line in self.order_line:
            if line.product_uom_qty % len(self.partner_id.child_ids) != 0:
                raise UserError(_("Les quantités doivent être divisibles par le nombre d'adresses de livraison."))

    def _split_order_lines(self, delivery_addresses):
        """Division des lignes de commande en plusieurs unités avec des adresses différentes."""
        _logger.info('Début de la division des lignes de commande')
        _logger.info('Adresses de livraison disponibles: %s', delivery_addresses.mapped('name'))
        
        # Calcul de la quantité par adresse
        total_quantity = sum(line.product_uom_qty for line in self.order_line)
        quantity_per_address = total_quantity / len(delivery_addresses)
        
        # Suppression des lignes existantes
        self.order_line.unlink()
        
        # Création des nouvelles lignes
        for address in delivery_addresses:
            for product in self.order_line.mapped('product_id'):
                self.env['sale.order.line'].create({
                    'order_id': self.id,
                    'product_id': product.id,
                    'product_uom_qty': quantity_per_address,
                    'product_uom': product.uom_id.id,
                    'partner_id': address.id,
                    'name': f"{product.name} - Livraison à {address.name}",
                    'price_unit': product.list_price,
                    'tax_id': [(6, 0, product.taxes_id.ids)],
                    'discount': 0.0,
                })
                _logger.info('Nouvelle ligne créée pour %s - Quantité: %s', address.name, quantity_per_address)

    def _create_delivery_after_split(self):
        """Création des BL après division des lignes de commande."""
        _logger.info('Création des BL après division')
        return super(SaleOrder, self).action_confirm()

    def _check_no_picking_created(self):
        """Vérifie si des BL ont été créés malgré le contexte."""
        if self.picking_ids:
            _logger.warning("BL créés en mode dispatch malgré le contexte no_picking=True")
            _logger.warning("BL concernés: %s", self.picking_ids.mapped('name'))
            # Annulation des BL créés par erreur
            for picking in self.picking_ids:
                if picking.state not in [STATE_CANCEL, STATE_DONE]:
                    picking.action_cancel()
                    _logger.info("BL %s annulé avec succès", picking.name)

    def _get_dispatch_context(self):
        """Retourne le contexte spécifique pour le mode dispatch."""
        return {
            'no_picking': True,
            'no_stock_move': True,
            'skip_stock_move': True,
            'skip_delivery': True,
            'skip_validation': True
        }

    def action_confirm(self):
        """Surcharge de la méthode de confirmation pour gérer la division des lignes de commande."""
        _logger.info('=== Début de action_confirm() ===')
        _logger.info('Commande de vente: %s', self.name)
        _logger.info('État actuel: %s', self.state)
        _logger.info('Mode de livraison: %s', self.delivery_mode)
        
        self._log_order_lines()
        
        if self.delivery_mode == DELIVERY_MODE_DISPATCH:
            _logger.info('Mode dispatch activé - Division des lignes de commande')
            
            # Vérification des adresses de livraison disponibles
            delivery_addresses = self._get_delivery_addresses()
            if not delivery_addresses:
                raise UserError(_("Aucune adresse de livraison disponible pour le mode dispatch."))
            
            # Division des lignes de commande
            self._split_order_lines(delivery_addresses)
            
            # Création des BL après division
            result = self._create_delivery_after_split()
        else:
            _logger.info('Mode standard activé - Génération automatique de BL')
            result = super(SaleOrder, self).action_confirm()
        
        self._log_order_lines()
        _logger.info('État après confirmation: %s', self.state)
        _logger.info('=== Fin de action_confirm() ===')
        return result

    def _get_delivery_addresses(self):
        """Récupère les adresses de livraison disponibles."""
        return self.env['res.partner'].search([
            ('parent_id', '=', self.partner_id.id),
            ('type', '=', 'delivery'),
            ('active', '=', True)
        ])

    def _action_launch_stock_rule(self):
        """Lancement du groupe de règles de stock avec des valeurs requises/personnalisées."""
        _logger.info('=== Début de _action_launch_stock_rule() ===')
        _logger.info('Commande de vente: %s', self.name)
        _logger.info('Mode de livraison: %s', self.delivery_mode)
        
        if self.delivery_mode == DELIVERY_MODE_DISPATCH:
            _logger.info('Mode dispatch activé - Pas de génération de BL')
            return
        
        _logger.info('Mode standard activé - Génération de BL')
        super(SaleOrder, self)._action_launch_stock_rule()
        
        _logger.info('=== Fin de _action_launch_stock_rule() ===')

    def _create_delivery(self):
        """Override pour empêcher la création de BL en mode dispatch."""
        _logger.info('=== Début de _create_delivery() ===')
        _logger.info('Commande de vente: %s', self.name)
        _logger.info('Mode de livraison: %s', self.delivery_mode)
        
        if self.delivery_mode == DELIVERY_MODE_DISPATCH:
            _logger.info('Mode dispatch activé - Pas de création de BL')
            return False
        
        _logger.info('Mode standard activé - Création de BL')
        return super(SaleOrder, self)._create_delivery() 