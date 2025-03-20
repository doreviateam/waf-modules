from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
from itertools import groupby
from operator import itemgetter

_logger = logging.getLogger(__name__)

class SaleLineDispatch(models.Model):
    _name = 'sale.line.dispatch'
    _description = 'Dispatch Line'
    _rec_name = 'display_name'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

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

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Dispatch',
        required=True,
        ondelete='cascade'
    )

    dispatch_state = fields.Selection(
        related='dispatch_id.state',
        string='Dispatch Status',
        store=True,
        readonly=True
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
        domain="[('order_id', '=', sale_order_id), ('remaining_qty', '>', 0)]"
    )

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Delivery Address',
        domain="[('type', '=', 'delivery')]",
        required=True
    )

    delivery_contact_display = fields.Char(
        string='Delivery Point',
        compute='_compute_delivery_contact_display',
        store=True
    )

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
        store=True
    )

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        store=True
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id'
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order',
        copy=False
    )

    stakeholder_id = fields.Many2one(
        'res.partner',
        string='Stakeholder',
        required=True,
        tracking=True,
        default=lambda self: self.sale_order_id.partner_id,
        domain="[('is_company', '=', True)]",
        help="Stakeholder benefiting from the order"
    )

    scheduled_date = fields.Date(
        string='Scheduled Date',
        required=True,
        tracking=True,
        default=fields.Date.context_today
    )

    sequence = fields.Integer(string='Sequence', default=10)

    company_id = fields.Many2one(
        'res.company',
        related='sale_order_id.company_id',
        store=True,
        tracking=True
    )

    remaining_qty = fields.Float(
        string='Remaining Quantity',
        compute='_compute_remaining_qty',
        store=True,
        help="Remaining quantity that can be dispatched"
    )

    @api.depends('dispatch_id.name', 'sale_order_line_id.product_id.name')
    def _compute_name(self):
        for line in self:
            if line.dispatch_id and line.sale_order_line_id:
                line.name = f"{line.dispatch_id.name}/{line.sale_order_line_id.product_id.name}"
            else:
                line.name = "/"

    @api.depends('product_id', 'partner_shipping_id', 'product_uom_qty')
    def _compute_display_name(self):
        for line in self:
            parts = []
            if line.product_id:
                parts.append(line.product_id.name)
            if line.product_uom_qty:
                parts.append(str(line.product_uom_qty))
            if line.partner_shipping_id:
                parts.append(line.partner_shipping_id.display_name)
            line.display_name = " - ".join(filter(None, parts)) or "/"

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit

    @api.depends('partner_shipping_id', 'partner_shipping_id.name', 'partner_shipping_id.zip', 'partner_shipping_id.city', 'partner_shipping_id.parent_id')
    def _compute_delivery_contact_display(self):
        """Calcule l'affichage formaté de l'adresse de livraison.
        Format: "Contact Name (34000 Montpellier)" ou "Contact Name" si pas de localisation
        Pour les contacts liés à une société, le nom de la société est retiré du nom du contact.
        """
        for record in self:
            if not record.partner_shipping_id:
                record.delivery_contact_display = False
                continue

            # Récupération et formatage du nom du contact
            contact = record.partner_shipping_id
            name = contact.name or ''

            # Si c'est un contact d'une société, on retire le nom de la société
            if contact.parent_id and contact.parent_id.name:
                parent_name = contact.parent_id.name.strip()
                if name.startswith(parent_name):
                    # Retire le nom de la société et nettoie les caractères spéciaux restants
                    name = name.replace(parent_name, '', 1).strip(' ,-/')
                    # Si le nom est vide après nettoyage, utiliser le nom original
                    if not name:
                        name = contact.name

            # Construction de la partie localisation
            location_parts = []
            if contact.zip:
                location_parts.append(contact.zip.strip())
            if contact.city:
                location_parts.append(contact.city.strip())

            # Assemblage du résultat final
            if location_parts:
                record.delivery_contact_display = f"{name} ({' '.join(location_parts)})"
            else:
                record.delivery_contact_display = name

    @api.depends('sale_order_line_id')
    def _compute_product_id(self):
        for record in self:
            record.product_id = record.sale_order_line_id.product_id if record.sale_order_line_id else False

    @api.depends('sale_order_line_id')
    def _compute_product_uom(self):
        for record in self:
            record.product_uom = record.sale_order_line_id.product_uom if record.sale_order_line_id else False

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        self.sale_order_line_id = False
        self.partner_shipping_id = False

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id(self):
        if self.sale_order_line_id:
            # Calculer la quantité déjà dispatchée pour cette ligne de commande
            domain = [
                ('sale_order_line_id', '=', self.sale_order_line_id.id),
                ('state', 'not in', ['cancel']),
                ('dispatch_id', '!=', self.dispatch_id.id)  # Exclure le dispatch actuel
            ]
            
            # Récupérer les lignes existantes dans la base de données (autres dispatches)
            existing_lines = self.env['sale.line.dispatch'].search(domain)
            
            # Récupérer les lignes du dispatch actuel (sauf la ligne en cours)
            current_dispatch_lines = self.dispatch_id.line_ids.filtered(
                lambda l: l.sale_order_line_id == self.sale_order_line_id 
                and l.state != 'cancel'
                and l != self
            )
            
            # Calculer la quantité totale dispatchée
            dispatched_qty = 0.0
            
            # Ajouter les quantités des autres dispatches
            for line in existing_lines:
                dispatched_qty += self._convert_qty_uom(
                    line.product_uom_qty,
                    line.product_uom,
                    self.sale_order_line_id.product_uom
                )
            
            # Ajouter les quantités du dispatch actuel
            for line in current_dispatch_lines:
                dispatched_qty += self._convert_qty_uom(
                    line.product_uom_qty,
                    line.product_uom,
                    self.sale_order_line_id.product_uom
                )
            
            # Calculer la quantité restante
            remaining = self.sale_order_line_id.product_uom_qty - dispatched_qty
            self.product_uom_qty = max(0, remaining)

    @api.constrains('product_uom_qty')
    def _check_quantity(self):
        for line in self:
            if line.product_uom_qty <= 0:
                raise ValidationError(_("Quantity must be greater than 0."))

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
                raise ValidationError(_('The delivery address must be a contact of a company.'))

    @api.constrains('state', 'dispatch_id')
    def _check_dispatch_state(self):
        """Vérifie la cohérence des états entre la ligne et son dispatch."""
        for line in self:
            if line.state in ['confirmed', 'done'] and line.dispatch_id.state == 'draft':
                raise ValidationError(_("Cannot have confirmed or done lines in a draft dispatch."))
            if line.state == 'done' and line.dispatch_id.state != 'done':
                raise ValidationError(_("Cannot have done lines in a non-done dispatch."))

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
        self._check_access_rights('write')
        
        # Vérifier l'état du dispatch parent
        for line in self:
            if line.dispatch_id.state != 'draft':
                raise UserError(_("Cannot confirm lines when dispatch is not in draft state."))

        # Supprimer silencieusement les lignes avec quantité nulle
        lines_to_unlink = self.filtered(lambda l: l.product_uom_qty <= 0)
        if lines_to_unlink:
            lines_to_unlink.unlink()
            # Si toutes les lignes ont été supprimées, arrêter ici
            if not (self - lines_to_unlink):
                return True

        def groupby_key(line):
            return (line.partner_shipping_id.id, line.scheduled_date, line.sale_order_id.id)
        
        # Ne traiter que les lignes non supprimées
        remaining_lines = self - lines_to_unlink
        sorted_lines = remaining_lines.sorted(key=lambda l: (l.partner_shipping_id.id, l.scheduled_date, l.sale_order_id.id))
        
        for (address_id, scheduled_date, order_id), lines in groupby(sorted_lines, key=groupby_key):
            lines = list(lines)
            if not lines:
                continue

            first_line = lines[0]
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('warehouse_id.company_id', '=', first_line.sale_order_id.company_id.id)
            ], limit=1)

            if not picking_type:
                raise UserError(_("No outgoing picking type found for company %s") % first_line.sale_order_id.company_id.name)

            picking_vals = {
                'partner_id': first_line.partner_shipping_id.id,
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'scheduled_date': scheduled_date,
                'origin': f"{first_line.sale_order_id.name}/{first_line.dispatch_id.name}",
                'move_ids': [],
                'company_id': first_line.company_id.id,
            }

            for line in lines:
                picking_vals['move_ids'].append((0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'location_id': picking_type.default_location_src_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id,
                    'sale_line_id': line.sale_order_line_id.id,
                    'company_id': line.company_id.id,
                }))

            picking = self.env['stock.picking'].create(picking_vals)
            lines_to_update = self.browse([l.id for l in lines])
            lines_to_update.write({
                'picking_id': picking.id,
                'state': 'confirmed'
            })

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
        self._check_access_rights('write')
        for line in self:
            if line.state not in ['draft', 'confirmed']:
                raise UserError(_("Only draft or confirmed lines can be cancelled."))
            if line.picking_id and line.picking_id.state not in ['draft', 'cancel']:
                raise UserError(_("Cannot cancel a line with an active delivery order."))
            line.write({'state': 'cancel'})
            _logger.info(f"Dispatch line {line.display_name} cancelled.")

    def action_draft(self):
        self._check_access_rights('write')
        for line in self:
            if line.state != 'cancel':
                raise UserError(_("Only cancelled lines can be set back to draft."))
            line.write({'state': 'draft'})
            _logger.info(f"Dispatch line {line.display_name} set back to draft.")

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty(self):
        """Suppression de la méthode qui générait le message d'avertissement"""
        pass

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        return super().write(vals)

    def unlink(self):
        """Gère la suppression des lignes de dispatch."""
        for line in self:
            if line.state != 'draft':
                raise UserError(_("Vous ne pouvez supprimer que les lignes en brouillon."))
        return super().unlink()
