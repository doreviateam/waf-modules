from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime
from odoo.tools import float_compare

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
    _description = 'Sales Order'

    delivery_mode = fields.Selection([
        (DELIVERY_MODE_STANDARD, 'Standard'),
        (DELIVERY_MODE_DISPATCH, 'Dispatch')
    ], string='Mode de livraison', 
       default=DELIVERY_MODE_STANDARD, 
       required=True,
       tracking=True)

    locked = fields.Boolean(string='Verrouillé', default=False)

    has_delivery_addresses = fields.Boolean(
        string="A des adresses de livraison",
        compute="_compute_has_delivery_addresses",
        store=True
    )

    delivery_addresses = fields.Many2many(
        'partner.address',
        string='Adresses de livraison',
        compute='_compute_delivery_addresses',
        store=False
    )

    dispatch_ids = fields.One2many(
        'sale.line.dispatch',
        'sale_order_id',
        string='Dispatches'
    )
    
    dispatch_completion = fields.Float(
        string='Progression dispatch', 
        compute='_compute_dispatch_completion',
        store=True,
        help="Pourcentage des quantités dispatchées"
    )

    dispatch_count = fields.Integer(
        string='Nombre de dispatches',
        compute='_compute_dispatch_count',
        store=True
    )

    dispatch_progress = fields.Float(
        string='% Dispatché',
        compute='_compute_dispatch_progress',
        store=True,
        help="Pourcentage total des quantités dispatchées"
    )

    is_dispatch_mode = fields.Boolean('Mode dispatch', default=False)

    @api.depends('partner_id')
    def _compute_delivery_addresses(self):
        for order in self:
            order.delivery_addresses = self.env['partner.address'].search([
                ('partner_ids', 'in', [order.partner_id.id]),
                ('type', '=', 'delivery'),
                ('active', '=', True)
            ])

    @api.constrains('delivery_mode', 'state')
    def _check_delivery_mode_state(self):
        """Vérifie que le mode de livraison est cohérent avec l'état de la commande."""
        for order in self:
            # On ne vérifie que le changement de mode, pas la confirmation
            if order.state not in [STATE_DRAFT, STATE_SENT] and order.delivery_mode != order._origin.delivery_mode:
                raise ValidationError(_("Le mode dispatch ne peut être modifié que sur des devis non confirmés."))

    @api.onchange('delivery_mode')
    def _onchange_delivery_mode(self):
        """Gère le changement de mode de livraison."""
        if self.state not in [STATE_DRAFT, STATE_SENT]:
            raise UserError(_("Le mode de livraison ne peut être modifié que sur un devis non confirmé."))
        
        if self.delivery_mode == DELIVERY_MODE_DISPATCH:
            self._validate_dispatch_mode()

    @api.onchange('partner_id', 'delivery_mode')
    def _onchange_partner_delivery_mode(self):
        if self.delivery_mode == DELIVERY_MODE_DISPATCH and self.partner_id:
            # Recherche automatique des adresses de livraison associées au partenaire
            addresses = self.env['partner.address'].search([
                ('partner_ids', 'in', [self.partner_id.id]),
                ('type', '=', 'delivery'),
                ('active', '=', True)
            ])
            self.delivery_addresses = addresses
        else:
            self.delivery_addresses = False

    def _log_order_lines(self):
        """Log les informations des lignes de commande pour le debugging."""
        _logger.info('=== État des lignes de commande ===')
        _logger.info('Commande: %s - Mode: %s - État: %s', 
                    self.name, self.delivery_mode, self.state)
        
        for line in self.order_line:
            _logger.info('Ligne: %s - Quantité: %s - Prix: %s', 
                        line.product_id.name, 
                        line.product_uom_qty,
                        line.price_unit)
            
            if line.move_ids:
                _logger.info('Mouvements de stock:')
                for move in line.move_ids:
                    _logger.info('  - %s: %s', move.state, move.product_uom_qty)

    def _validate_dispatch_mode(self):
        """Valide que le mode dispatch peut être utilisé."""
        _logger.info('=== Validation du mode dispatch ===')
        
        # On ne vérifie les adresses que lors de la confirmation
        if self.state in [STATE_SALE, STATE_DONE]:
            if not self.delivery_addresses:
                raise UserError(_("Le mode dispatch nécessite des adresses de livraison associées au client."))
            
            _logger.info('Adresses de livraison trouvées: %s', len(self.delivery_addresses))
            
            # Vérification des quantités
            for line in self.order_line:
                if line.product_uom_qty <= 0:
                    raise UserError(_("Les quantités doivent être supérieures à 0."))
                
                if line.product_uom_qty % len(self.delivery_addresses) != 0:
                    raise UserError(_(
                        "La quantité de '%s' (%s) doit être divisible par le nombre d'adresses (%s)."
                    ) % (line.product_id.name, line.product_uom_qty, len(self.delivery_addresses)))

    def _split_order_lines(self):
        """Divise les lignes de commande en plusieurs unités avec des adresses différentes."""
        _logger.info('=== Début de la division des lignes de commande ===')
        
        if not self.delivery_addresses:
            raise UserError(_("Aucune adresse de livraison disponible pour le mode dispatch."))

        # Sauvegarder les produits avant suppression des lignes
        original_lines = self.order_line
        _logger.info('Lignes originales à diviser: %s', len(original_lines))

        try:
            # Suppression des lignes existantes
            self.order_line.unlink()

            # Création des nouvelles lignes
            for address in self.delivery_addresses:
                for line in original_lines:
                    quantity_per_address = line.product_uom_qty / len(self.delivery_addresses)
                    
                    # Création de la nouvelle ligne
                    new_line = self.env['sale.order.line'].create({
                        'order_id': self.id,
                        'product_id': line.product_id.id,
                        'product_uom_qty': quantity_per_address,
                        'product_uom': line.product_uom.id,
                        'name': f"{line.product_id.name} - Livraison à {address.name}",
                        'price_unit': line.price_unit,
                        'tax_id': [(6, 0, line.tax_id.ids)],
                        'discount': line.discount,
                        'partner_id': address.id,
                    })
                    
                    _logger.info("Nouvelle ligne créée : Produit %s - Adresse %s - Quantité %s",
                                line.product_id.name, address.name, quantity_per_address)
                    
        except Exception as e:
            _logger.error("Erreur lors de la division des lignes : %s", str(e))
            raise UserError(_("Une erreur est survenue lors de la division des lignes de commande."))

    def _create_delivery_after_split(self):
        """Création des BL après division des lignes de commande."""
        _logger.info('=== Création des BL après division ===')
        try:
            return super(SaleOrder, self).action_confirm()
        except Exception as e:
            _logger.error("Erreur lors de la création des BL : %s", str(e))
            raise UserError(_("Une erreur est survenue lors de la création des bons de livraison."))

    def _group_dispatches(self):
        """Regroupe les dispatches par date et adresse."""
        self.ensure_one()
        if self.delivery_mode != DELIVERY_MODE_DISPATCH:
            return

        # Regrouper tous les dispatches non groupés
        dispatches = self.dispatch_ids.filtered(lambda d: not d.dispatch_group_id and d.state != STATE_CANCEL)
        
        # Créer un dictionnaire pour regrouper les dispatches
        dispatch_groups = {}
        for dispatch in dispatches:
            key = (dispatch.scheduled_date, dispatch.delivery_address_id.id)
            if key not in dispatch_groups:
                dispatch_groups[key] = self.env['sale.line.dispatch']
            dispatch_groups[key] |= dispatch

        # Créer ou mettre à jour les groupes
        for (scheduled_date, address_id), group_dispatches in dispatch_groups.items():
            if not group_dispatches:
                continue

            # Chercher un groupe existant
            existing_group = self.env['sale.dispatch.group'].search([
                ('sale_order_id', '=', self.id),
                ('delivery_address_id', '=', address_id),
                ('scheduled_date', '=', scheduled_date),
                ('state', '=', 'draft')
            ], limit=1)

            if existing_group:
                # Ajouter les dispatches au groupe existant
                group_dispatches.write({'dispatch_group_id': existing_group.id})
            else:
                # Créer un nouveau groupe
                group = self.env['sale.dispatch.group'].create({
                    'sale_order_id': self.id,
                    'delivery_address_id': address_id,
                    'scheduled_date': scheduled_date,
                    'state': 'draft'
                })
                group_dispatches.write({'dispatch_group_id': group.id})

    def action_confirm(self):
        """Surcharge de la confirmation de commande."""
        for order in self:
            if order.delivery_mode == 'dispatch':
                if order.dispatch_progress < 100:
                    raise UserError(_(
                        "La commande %s ne peut pas être confirmée car elle n'est pas entièrement dispatchée."
                    ) % order.name)
                
                # Confirmer la commande
                res = super().action_confirm()
                
                # Regrouper automatiquement les dispatches
                order._group_dispatches()
                
                return res
            return super().action_confirm()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if any(vals.get('dispatch_ids') for vals in vals_list):
                record._group_dispatches()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'dispatch_ids' in vals:
            for order in self:
                order._group_dispatches()
        return res

    def _compute_has_delivery_addresses(self):
        """Détermine si le client a des adresses de livraison."""
        for order in self:
            order.has_delivery_addresses = bool(order.delivery_addresses)

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        if self.delivery_mode == DELIVERY_MODE_DISPATCH:
            return True
        return super()._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)

    def _create_delivery(self):
        """Empêche la création automatique des BL en mode dispatch."""
        if self.delivery_mode == DELIVERY_MODE_DISPATCH:
            _logger.info("Mode dispatch activé - Pas de création automatique du bon de livraison.")
            return False
        return super(SaleOrder, self)._create_delivery()

    @api.depends('order_line.product_uom_qty', 'dispatch_ids.product_uom_qty', 'dispatch_ids.state')
    def _compute_dispatch_completion(self):
        for order in self:
            if order.delivery_mode != DELIVERY_MODE_DISPATCH or not order.order_line:
                order.dispatch_completion = 0.0
                continue

            total_ordered = sum(order.order_line.mapped('product_uom_qty'))
            total_dispatched = sum(order.dispatch_ids.filtered(
                lambda d: d.state != STATE_CANCEL
            ).mapped('product_uom_qty'))

            order.dispatch_completion = (total_dispatched / total_ordered * 100) if total_ordered else 0.0

    @api.depends('dispatch_ids')
    def _compute_dispatch_count(self):
        """Calcule le nombre de dispatches liés à la commande."""
        for order in self:
            order.dispatch_count = len(order.dispatch_ids)

    @api.depends('order_line.product_uom_qty', 'dispatch_ids.product_uom_qty', 'dispatch_ids.state')
    def _compute_dispatch_progress(self):
        for order in self:
            if order.delivery_mode != DELIVERY_MODE_DISPATCH or not order.order_line:
                order.dispatch_progress = 0.0
                continue

            total_ordered = sum(order.order_line.mapped('product_uom_qty'))
            total_dispatched = sum(order.dispatch_ids.filtered(
                lambda d: d.state != STATE_CANCEL
            ).mapped('product_uom_qty'))

            order.dispatch_progress = (total_dispatched / total_ordered * 100) if total_ordered else 0.0

    def action_view_dispatches(self):
        """Ouvre la vue des dispatches liés à la commande."""
        self.ensure_one()
        return {
            'name': _('Dispatches'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.line.dispatch',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id}
        }

    def action_create_dispatches(self):
        """Crée les dispatches pour les lignes de commande."""
        self.ensure_one()
        
        if self.state != 'sale':
            raise UserError(_("Les dispatches ne peuvent être créés que pour une commande confirmée."))
            
        if self.delivery_mode != DELIVERY_MODE_DISPATCH:
            raise UserError(_("Les dispatches ne peuvent être créés qu'en mode dispatch."))

        # Vérifier si toutes les lignes sont déjà dispatchées
        for line in self.order_line:
            dispatched_qty = sum(self.dispatch_ids.filtered(
                lambda d: d.sale_order_line_id == line and d.state != STATE_CANCEL
            ).mapped('product_uom_qty'))
            
            if dispatched_qty >= line.product_uom_qty:
                raise UserError(_(
                    "La ligne '%s' est déjà entièrement dispatchée.\n"
                    "Quantité commandée : %s\n"
                    "Quantité dispatchée : %s"
                ) % (line.product_id.name, line.product_uom_qty, dispatched_qty))

        # Ouvrir l'assistant de création de dispatch
        return {
            'name': _('Créer Dispatches'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.line.dispatch',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_partner_id': self.partner_id.id,
            }
        }

    def action_open_mass_dispatch_wizard(self):
        self.ensure_one()
        
        # Ne vérifier les dispatches existants que lors de l'ouverture initiale
        if self._context.get('is_initial_step', True):
            existing_dispatches = self.dispatch_ids.filtered(lambda d: d.state != STATE_CANCEL)
            if existing_dispatches:
                message = _("Des dispatches existent déjà pour cette commande :\n\n")
                for dispatch in existing_dispatches:
                    message += _(
                        "- Produit : %s, Quantité : %s, Adresse : %s\n",
                        dispatch.product_id.name,
                        dispatch.product_uom_qty,
                        dispatch.delivery_address_id.name
                    )
                message += _("\nVoulez-vous continuer ?")
                
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Création dispatches'),
                    'res_model': 'mass.dispatch.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_sale_order_id': self.id,
                        'default_warning_message': message,
                        'is_initial_step': True
                    }
                }
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Création dispatches'),
            'res_model': 'mass.dispatch.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'is_initial_step': self._context.get('is_initial_step', True)
            }
        }

    def action_open_dispatch_group_wizard(self):
        self.ensure_one()
        return {
            'name': _('Regrouper les dispatches'),
            'type': 'ir.actions.act_window',
            'res_model': 'dispatch.group.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            }
        }

    @api.depends('order_line.dispatch_ids', 'order_line.product_uom_qty')
    def _compute_dispatch_status(self):
        for order in self:
            all_lines_dispatched = True
            for line in order.order_line:
                dispatched_qty = sum(
                    d.product_uom_qty 
                    for d in line.dispatch_ids 
                    if d.state != 'cancel'
                )
                if dispatched_qty < line.product_uom_qty:
                    all_lines_dispatched = False
                    break
            
            if all_lines_dispatched:
                # Si tout est dispatché, on peut confirmer les dispatches
                order.dispatch_ids.action_confirm()

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    dispatch_ids = fields.One2many('sale.line.dispatch', 'sale_order_line_id', string='Dispatches')
    dispatched_qty = fields.Float(
        string='Quantité dispatchée',
        compute='_compute_dispatched_qty',
        store=True
    )

    @api.depends('dispatch_ids.product_uom_qty', 'dispatch_ids.state')
    def _compute_dispatched_qty(self):
        for line in self:
            line.dispatched_qty = sum(
                dispatch.product_uom_qty 
                for dispatch in line.dispatch_ids 
                if dispatch.state != STATE_CANCEL
            )