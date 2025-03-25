from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare, float_round
from odoo.tools import float_is_zero
import logging
from itertools import groupby
from operator import itemgetter

_logger = logging.getLogger(__name__)

class SaleLineDispatch(models.Model):
    """Modèle gérant les lignes de dispatch des commandes de vente.
    
    Une ligne de dispatch représente une partie d'une ligne de commande qui sera
    livrée à une adresse spécifique, pour un stakeholder spécifique, à une date donnée.
    """
    _name = 'sale.line.dispatch'
    _description = 'Dispatch Line'
    _rec_name = 'display_name'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # region Champs d'identification
    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    # endregion

    # region Relations principales
    dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Dispatch',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Order',
        related='dispatch_id.sale_order_id',
        store=True,
        readonly=True
    )

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Order Line',
        required=True,
        domain="[('order_id', '=', sale_order_id), ('remaining_qty_line', '>', 0)]",
        tracking=True
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order',
        copy=False,
        readonly=True,
        tracking=True
    )
    # endregion

    # region Informations produit et quantités
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        compute='_compute_product_id',
        store=True,
        readonly=True
    )

    product_uom = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        compute='_compute_product_uom',
        store=True,
        readonly=True
    )

    product_uom_qty = fields.Float(
        string='Quantity',
        required=True,
        tracking=True,
        copy=False
    )

    price_unit = fields.Float(
        related='sale_order_line_id.price_unit',
        string='Unit Price',
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        string='Currency',
        store=True,
        readonly=True
    )

    company_id = fields.Many2one(
        related='sale_order_id.company_id',
        string='Company',
        store=True,
        readonly=True
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id'
    )
    # endregion

    # region Partenaires et adresses
    stakeholder_id = fields.Many2one(
        'res.partner',
        string='Stakeholder',
        required=True,
        tracking=True,
        domain="[('is_company', '=', True)]",
        help="Stakeholder benefiting from the order"
    )

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Delivery Address',
        required=True,
        tracking=True,
        domain="[('type', '=', 'delivery'), ('parent_id', '=', stakeholder_id)]",
        help="Delivery address for this line"
    )

    delivery_contact_display = fields.Char(
        string='Delivery Point',
        compute='_compute_delivery_contact_display',
        store=True
    )
    # endregion

    # region États et suivi
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('picking_created', 'BL Créé'),
        ('picking_assigned', 'BL Réservé'),
        ('picking_done', 'BL Terminé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État',
       default='draft',
       required=True,
       tracking=True,
       copy=False,
       help="États de la ligne de dispatch:\n"
            "- Brouillon: Ligne nouvellement créée\n"
            "- Confirmé: Ligne validée\n"
            "- BL Créé: Bon de livraison créé\n"
            "- BL Réservé: Stock réservé\n"
            "- BL Terminé: Livraison effectuée\n"
            "- Terminé: Processus terminé\n"
            "- Annulé: Ligne annulée"
    )

    dispatch_state = fields.Selection(
        related='dispatch_id.state',
        string='État du dispatch',
        store=True,
        readonly=True
    )

    # region Livraison et planification
    scheduled_date = fields.Date(
        string='Date prévue',
        required=True,
        tracking=True,
        # default=fields.Date.context_today
    )
    # endregion

    # region Autres informations
    # endregion

    # region Compute methods
    @api.depends('sale_order_line_id.product_id')
    def _compute_product_id(self):
        for record in self:
            record.product_id = record.sale_order_line_id.product_id

    @api.depends('sale_order_line_id.product_uom')
    def _compute_product_uom(self):
        for record in self:
            record.product_uom = record.sale_order_line_id.product_uom

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_amount(self):
        """Calcule le sous-total de la ligne."""
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit

    @api.depends('partner_shipping_id')
    def _compute_delivery_contact_display(self):
        for record in self:
            if record.partner_shipping_id:
                record.delivery_contact_display = record.partner_shipping_id.display_name
            else:
                record.delivery_contact_display = False

    @api.depends('dispatch_id.name', 'sale_order_line_id.product_id.display_name')
    def _compute_name(self):
        for record in self:
            if record.dispatch_id and record.sale_order_line_id.product_id:
                record.name = f"{record.dispatch_id.name}/{record.sale_order_line_id.product_id.display_name}"
            else:
                record.name = _('New')

    @api.depends('name', 'sale_order_id.name', 'product_id.display_name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.sale_order_id.name} - {record.product_id.display_name}"

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        self.sale_order_line_id = False
        self.partner_shipping_id = False

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id(self):
        """Met à jour la quantité proposée en fonction de la quantité restante à dispatcher."""
        if not self.sale_order_line_id:
            self.product_uom_qty = 0.0
            return

        # Calculer la quantité déjà dispatchée dans le dispatch courant
        current_dispatch_qty = sum(
            line.product_uom_qty
            for line in self.dispatch_id.line_ids
            if line.sale_order_line_id == self.sale_order_line_id
            and line.state != 'cancel'
            and not line._origin.id  # Seulement les nouvelles lignes pas encore sauvegardées
        )

        # Calculer la quantité restante en tenant compte des lignes en cours
        remaining = self.sale_order_line_id.remaining_qty_line - current_dispatch_qty
        self.product_uom_qty = max(0.0, remaining)

    @api.constrains('partner_shipping_id', 'stakeholder_id')
    def _check_partner_shipping_address(self):
        """Vérifie que l'adresse de livraison est bien enregistrée dans le système centralisé
        et liée au stakeholder."""
        PartnerAddress = self.env['partner.address']
        for record in self:
            # Rechercher l'adresse centralisée par les informations de l'adresse
            address = PartnerAddress.search([
                ('name', '=', record.partner_shipping_id.name),
                ('zip', '=', record.partner_shipping_id.zip),
                ('city', '=', record.partner_shipping_id.city),
            ], limit=1)
            
            if not address:
                raise ValidationError(_(
                    'The delivery address must be registered in the centralized address system. '
                    'Please create or update a partner.address record for this address first.'
                ))
            
            # Vérifier que le stakeholder est bien lié à cette adresse
            if record.stakeholder_id.id not in address.partner_ids.ids:
                raise ValidationError(_(
                    'The selected delivery address is not linked to %(stakeholder)s in the centralized address system. '
                    'Please add the stakeholder to the address partners first.',
                    stakeholder=record.stakeholder_id.name
                ))

    @api.constrains('sale_order_line_id', 'sale_order_id')
    def _check_sale_order_line(self):
        for dispatch in self:
            if dispatch.sale_order_line_id.order_id != dispatch.sale_order_id:
                raise ValidationError(_("The order line must belong to the selected order."))

    def _convert_qty_uom(self, qty, from_uom, to_uom):
        """Convertit une quantité d'une unité de mesure à une autre."""
        if not from_uom or not to_uom:
            return qty
        if from_uom == to_uom:
            return qty
        return from_uom._compute_quantity(qty, to_uom)

    @api.depends('sale_order_line_id.product_uom_qty', 'sale_order_line_id.dispatched_qty_line')
    def _compute_remaining_qty(self):
        for line in self:
            if not line.sale_order_line_id:
                line.remaining_qty = 0.0
                continue

            order_line = line.sale_order_line_id
            initial_qty = order_line.product_uom_qty
            
            # Calculer la quantité déjà dispatchée en tenant compte des UdM
            domain = [
                ('sale_order_line_id', '=', order_line.id),
                ('state', 'not in', ['cancel'])
            ]
            
            # Ne pas inclure l'enregistrement courant s'il existe déjà
            if isinstance(line.id, int):
                domain.append(('id', '!=', line.id))
            
            dispatched_lines = self.search(domain)
            dispatched_qty = sum(
                self._convert_qty_uom(
                    l.product_uom_qty,
                    l.product_uom,
                    order_line.product_uom
                )
                for l in dispatched_lines
            )

            line.remaining_qty = max(0, initial_qty - dispatched_qty)

    @api.constrains('product_uom_qty', 'sale_order_line_id')
    def _check_dispatch_quantity(self):
        for line in self:
            domain = [
                ('sale_order_line_id', '=', line.sale_order_line_id.id),
                ('state', 'not in', ['cancel']),
                ('id', '!=', line.id)
            ]
            
            other_lines = self.search(domain)
            other_lines_qty = sum(
                self._convert_qty_uom(
                    l.product_uom_qty,
                    l.product_uom,
                    line.sale_order_line_id.product_uom
                )
                for l in other_lines
            )
            
            current_line_qty = self._convert_qty_uom(
                line.product_uom_qty,
                line.product_uom,
                line.sale_order_line_id.product_uom
            )
            
            total_qty = other_lines_qty + current_line_qty
            
            if total_qty > line.sale_order_line_id.product_uom_qty:
                available_qty = line.sale_order_line_id.product_uom_qty - other_lines_qty
                raise ValidationError(_(
                    "Total dispatched quantity (%(total)s) cannot exceed "
                    "ordered quantity (%(ordered)s) for product %(product)s.\n"
                    "Available quantity: %(available)s",
                    total=total_qty,
                    ordered=line.sale_order_line_id.product_uom_qty,
                    available=max(0, available_qty),
                    product=line.product_id.display_name
                ))

    @api.constrains('partner_shipping_id')
    def _check_delivery_address_partner(self):
        for record in self:
            if record.partner_shipping_id and not record.partner_shipping_id.parent_id:
                raise ValidationError(_("The delivery address must be a contact of a company."))

    def _check_access_rights(self, operation):
        """Vérifie les droits d'accès pour une opération donnée."""
        self.check_access_rights(operation)
        self.check_access_rule(operation)

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No delivery order is associated with this line."))
            
        return {
            'name': _('Delivery Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'context': {'create': False},
        }

    def action_confirm(self):
        """Confirme la ligne de dispatch."""
        for line in self:
            if line.state == 'draft':
                line.write({'state': 'confirmed'})
                # Vérifier si toutes les lignes du dispatch sont confirmées
                if all(l.state in ['confirmed', 'done', 'cancel'] for l in line.dispatch_id.line_ids):
                    line.dispatch_id.write({'state': 'confirmed'})
        return True

    def action_done(self):
        self._check_access_rights('write')
        for line in self:
            if line.state != 'confirmed':
                raise UserError(_("Only confirmed lines can be marked as done."))
            if not line.picking_id.state == 'done':
                raise UserError(_("The delivery order must be done before marking the line as done."))
            line.write({'state': 'done'})
            _logger.info(f"Dispatch line {line.display_name} marked as done.")

    def action_cancel(self):
        """Annule la ligne de dispatch."""
        for line in self:
            if line.state not in ['done', 'cancel']:
                line.write({'state': 'cancel'})
                # Vérifier si toutes les lignes du dispatch sont annulées
                if all(l.state == 'cancel' for l in line.dispatch_id.line_ids):
                    line.dispatch_id.write({'state': 'cancel'})
        return True

    def action_set_to_draft(self):
        """Remet la ligne en brouillon."""
        for line in self:
            if line.state == 'done':
                raise ValidationError(_(
                    "La ligne %(name)s est terminée (état: %(state)s) et ne peut pas être remise en brouillon.",
                    name=line.display_name,
                    state=dict(line._fields['state'].selection).get(line.state)
                ))
            if line.state != 'cancel':
                raise ValidationError(_(
                    "Seules les lignes annulées peuvent être remises en brouillon. "
                    "La ligne %(name)s est dans l'état %(state)s.",
                    name=line.display_name,
                    state=dict(line._fields['state'].selection).get(line.state)
                ))
            
            line.write({'state': 'draft'})
            # Remettre le dispatch en brouillon si au moins une ligne est en brouillon
            if line.dispatch_id.state == 'cancel':
                line.dispatch_id.write({'state': 'draft'})
        return True

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty(self):
        """Suppression de la méthode qui générait le message d'avertissement"""
        pass

    @api.onchange('stakeholder_id')
    def _onchange_stakeholder_id(self):
        """Reset delivery address when stakeholder changes"""
        self.partner_shipping_id = False
        if self.stakeholder_id:
            return {
                'domain': {
                    'partner_shipping_id': [
                        ('type', '=', 'delivery'),
                        ('parent_id', '=', self.stakeholder_id.id)
                    ]
                }
            }
        return {'domain': {'partner_shipping_id': [('type', '=', 'delivery')]}}

    @api.model
    def _valid_field_parameter(self, field, name):
        return name == 'options' or super()._valid_field_parameter(field, name)

    @api.onchange('dispatch_id')
    def _onchange_dispatch_id(self):
        """Définit automatiquement le stakeholder quand il n'y en a qu'un seul disponible."""
        if self.dispatch_id and len(self.dispatch_id.stakeholder_ids) == 1:
            self.stakeholder_id = self.dispatch_id.stakeholder_ids[0]

    remaining_qty = fields.Float(
        string='Remaining Quantity',
        related='sale_order_line_id.remaining_qty_line',
        store=True,
        readonly=True
    )

    def _get_protected_states(self):
        """États dans lesquels la suppression est interdite."""
        return ['confirmed', 'done']

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la création pour initialiser l'état."""
        for vals in vals_list:
            # S'assurer que les nouvelles lignes sont toujours en brouillon
            vals['state'] = 'draft'
        return super().create(vals_list)

    def write(self, vals):
        """Surcharge de l'écriture pour empêcher la modification des lignes non-draft."""
        # Liste des champs techniques qui peuvent être modifiés quel que soit l'état
        technical_fields = {
            'picking_id',    # Lien avec le bon de livraison
            'state',         # État de la ligne
            'display_name',  # Champ calculé
            'message_ids',   # Chatter
            'message_follower_ids',  # Followers
            'activity_ids',  # Activités
        }

        # Si on ne modifie que des champs techniques, on laisse passer
        if all(field in technical_fields for field in vals.keys()):
            return super().write(vals)

        # Pour toute autre modification, on vérifie l'état
        for line in self:
            if line.state != 'draft':
                # On retire les champs techniques de la liste des champs modifiés
                business_fields = set(vals.keys()) - technical_fields
                if business_fields:
                    # Liste des champs qu'on essaie de modifier
                    field_labels = []
                    for field in business_fields:
                        field_label = self._fields[field].string if field in self._fields else field
                        field_labels.append(field_label)

                    raise ValidationError(_(
                        "La ligne %(name)s est dans l'état %(state)s et ne peut pas être modifiée.\n"
                        "Champs concernés : %(fields)s",
                        name=line.display_name,
                        state=dict(line._fields['state'].selection).get(line.state),
                        fields=', '.join(field_labels)
                    ))

        res = super().write(vals)
        if 'state' in vals:
            self._sync_dispatch_state()
        return res

    def _sync_dispatch_state(self):
        """Synchronise l'état du dispatch parent en fonction de l'état des lignes."""
        dispatches = self.mapped('dispatch_id')
        for dispatch in dispatches:
            if dispatch:
                states = dispatch.line_ids.mapped('state')
                if all(state == 'done' for state in states):
                    dispatch.write({'state': 'done'})
                elif all(state == 'cancel' for state in states):
                    dispatch.write({'state': 'cancel'})
                elif any(state == 'confirmed' for state in states):
                    dispatch.write({'state': 'confirmed'})
                elif all(state == 'draft' for state in states):
                    dispatch.write({'state': 'draft'})

    def unlink(self):
        """Surcharge de la suppression pour empêcher la suppression des lignes non brouillon."""
        for line in self:
            if line.state != 'draft':
                raise ValidationError(_(
                    "La ligne %(name)s est dans l'état %(state)s et ne peut pas être supprimée.",
                    name=line.display_name,
                    state=dict(line._fields['state'].selection).get(line.state)
                ))
            
            # Mettre à jour la quantité sur la ligne de commande
            if line.sale_order_line_id and line.product_uom_qty:
                # Convertir la quantité dans l'unité de mesure de la ligne de commande
                qty_to_add = line.product_uom._compute_quantity(
                    line.product_uom_qty,
                    line.sale_order_line_id.product_uom,
                    rounding_method='HALF-UP'
                )
                # Mettre à jour la quantité disponible sur la ligne de commande
                line.sale_order_line_id.write({
                    'remaining_qty_line': line.sale_order_line_id.remaining_qty_line + qty_to_add
                })
                _logger.info(
                    f"Updated remaining quantity for order line {line.sale_order_line_id.name}: "
                    f"added {qty_to_add} {line.sale_order_line_id.product_uom.name}"
                )
        
        return super().unlink()
