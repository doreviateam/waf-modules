from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
from itertools import groupby
from operator import itemgetter

_logger = logging.getLogger(__name__)

class SaleLineDispatch(models.Model):
    _name = 'sale.line.dispatch'
    _description = 'Ligne de dispatch'
    _rec_name = 'display_name'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Référence',
        compute='_compute_name',
        store=True
    )

    display_name = fields.Char(
        string='Nom affiché',
        compute='_compute_display_name',
        store=True
    )

    state = fields.Selection(
        related='dispatch_id.state',
        store=True,
        readonly=True)

    dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Dispatch',
        required=True,
        ondelete='cascade'
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Commande',
        related='dispatch_id.sale_order_id',
        store=True,
        readonly=True
    )

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Ligne de commande',
        required=True,
        domain="[('order_id', '=', sale_order_id), ('remaining_qty', '>', 0)]"
    )

    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Adresse de livraison',
        required=True,
        domain="[]"
    )

    product_id = fields.Many2one(
        'product.product',
        related='sale_order_line_id.product_id',
        store=True
    )

    product_uom = fields.Many2one(
        'uom.uom',
        related='sale_order_line_id.product_uom',
        string='Unité',
        store=True
    )

    product_uom_qty = fields.Float(
        string='Quantité',
        required=True,
        tracking=True,
        copy=False
    )

    price_unit = fields.Float(
        related='sale_order_line_id.price_unit',
        string='Prix unitaire',
        store=True
    )

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        store=True
    )

    company_id = fields.Many2one(
        'res.company',
        related='sale_order_id.company_id',
        store=True
    )

    price_subtotal = fields.Monetary(
        string='Sous-total',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id'
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Bon de livraison',
        copy=False
    )

    stakeholder_id = fields.Many2one(
        'res.partner',
        string='Stakeholder',
        required=True,
        tracking=True,
        default=lambda self: self.sale_order_id.partner_id,
        domain="[('is_company', '=', True)]", # On fait du B2B
        help="Partie prenante qui bénéficie de la commande"
    )

    scheduled_date = fields.Date(
        string='Date de livraison',
        required=True,
        tracking=True,
        default=fields.Date.context_today
    )

    def action_view_picking(self):
        """Affiche le bon de livraison associé."""
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("Aucun bon de livraison n'est associé à cette ligne."))
            
        return {
            'name': _('Bon de livraison'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'context': {'create': False},
        }

    def action_confirm(self):
        # Regrouper les lignes par adresse de livraison et date
        def groupby_key(line):
            return (line.delivery_address_id.id, line.scheduled_date, line.sale_order_id.id)
        
        # Trier les lignes pour assurer un regroupement correct
        sorted_lines = self.sorted(key=lambda l: (l.delivery_address_id.id, l.scheduled_date, l.sale_order_id.id))
        
        for (address_id, scheduled_date, order_id), lines in groupby(sorted_lines, key=groupby_key):
            lines = list(lines)  # Convertir l'itérateur en liste
            if not lines:
                continue

            first_line = lines[0]
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('warehouse_id.company_id', '=', first_line.sale_order_id.company_id.id)
            ], limit=1)

            # Créer un BL pour le groupe
            picking_vals = {
                'partner_id': first_line.delivery_address_id.main_partner_id.id,
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'scheduled_date': scheduled_date,
                'origin': first_line.sale_order_id.name,
                'move_ids': [],
            }

            # Ajouter les mouvements pour chaque ligne
            for line in lines:
                picking_vals['move_ids'].append((0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'location_id': picking_type.default_location_src_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id,
                    'sale_line_id': line.sale_order_line_id.id,
                }))

            # Créer le BL et le lier aux lignes
            picking = self.env['stock.picking'].create(picking_vals)
            lines_to_update = self.browse([l.id for l in lines])
            lines_to_update.write({
                'picking_id': picking.id,
                'state': 'confirmed'
            })

    def action_done(self):
        """Termine la ligne de dispatch."""
        for line in self:
            if line.state != 'confirmed':
                raise UserError(_("Seules les lignes confirmées peuvent être terminées."))
            line.write({'state': 'done'})
            _logger.info(f"Ligne de dispatch {line.display_name} terminée.")

    def action_cancel(self):
        """Annule la ligne de dispatch."""
        for line in self:
            if line.state not in ['draft', 'confirmed']:
                raise UserError(_("Seules les lignes en brouillon ou confirmées peuvent être annulées."))
            line.write({'state': 'cancel'})
            _logger.info(f"Ligne de dispatch {line.display_name} annulée.")

    def action_draft(self):
        """Remet la ligne en brouillon."""
        for line in self:
            if line.state != 'cancel':
                raise UserError(_("Seules les lignes annulées peuvent être remises en brouillon."))
            line.write({'state': 'draft'})
            _logger.info(f"Ligne de dispatch {line.display_name} remise en brouillon.")

    @api.depends('dispatch_id.name', 'sale_order_line_id.product_id.name')
    def _compute_name(self):
        for line in self:
            if line.dispatch_id and line.sale_order_line_id:
                line.name = f"{line.dispatch_id.name}/{line.sale_order_line_id.product_id.name}"
            else:
                line.name = "/"

    @api.depends('product_id', 'delivery_address_id', 'product_uom_qty')
    def _compute_display_name(self):
        for line in self:
            parts = []
            if line.product_id:
                parts.append(line.product_id.name)
            if line.product_uom_qty:
                parts.append(str(line.product_uom_qty))
            if line.delivery_address_id:
                parts.append(line.delivery_address_id.display_name)
            line.display_name = " - ".join(filter(None, parts)) or "/"

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        self.sale_order_line_id = False
        self.delivery_address_id = False

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id(self):
        if self.sale_order_line_id:
            initial_qty = self.sale_order_line_id.product_uom_qty
            
            # Calculer le total des lignes existantes ET nouvelles
            total_dispatched = 0
            
            # Lignes déjà enregistrées
            domain = [
                ('sale_order_line_id', '=', self.sale_order_line_id.id),
                ('state', 'not in', ['cancel']),
                ('id', '!=', self._origin.id)
            ]
            total_dispatched += sum(self.search(domain).mapped('product_uom_qty'))
            
            # Lignes en cours d'édition dans le même dispatch
            if self.dispatch_id:
                for line in self.dispatch_id.line_ids:
                    if (line.sale_order_line_id == self.sale_order_line_id 
                        and line.id != self._origin.id 
                        and not line.state == 'cancel'):
                        total_dispatched += line.product_uom_qty
            
            remaining_qty = initial_qty - total_dispatched
            
            if not self.product_uom_qty:
                self.product_uom_qty = max(0, remaining_qty)

    @api.constrains('product_uom_qty')
    def _check_quantity(self):
        for line in self:
            if line.product_uom_qty <= 0:
                raise ValidationError(_("La quantité doit être supérieure à 0."))

    @api.constrains('delivery_address_id', 'sale_order_id')
    def _check_delivery_address(self):
        for line in self:
            if not line.sale_order_id or not line.delivery_address_id:
                continue
            # Vérifier que l'adresse de livraison est dans les adresses du client
            if line.delivery_address_id.id not in line.sale_order_id.partner_id.address_ids.ids:
                raise ValidationError(_(
                    "L'adresse de livraison doit être une des adresses du client de la commande."
                ))

    @api.constrains('sale_order_line_id', 'sale_order_id')
    def _check_sale_order_line(self):
        """Vérifie que la ligne appartient bien à la commande."""
        for dispatch in self:
            if dispatch.sale_order_line_id.order_id != dispatch.sale_order_id:
                raise ValidationError(_(
                    "La ligne de commande doit appartenir à la commande sélectionnée."
                ))

    @api.constrains('product_uom_qty', 'sale_order_line_id')
    def _check_dispatch_quantity(self):
        for line in self:
            # Calculer le total des quantités en brouillon et confirmées
            domain = [
                ('sale_order_line_id', '=', line.sale_order_line_id.id),
                ('state', 'not in', ['cancel']),
                ('id', '!=', line.id)  # Exclure la ligne courante
            ]
            
            other_lines_qty = sum(self.search(domain).mapped('product_uom_qty'))
            total_qty = other_lines_qty + line.product_uom_qty
            
            if total_qty > line.sale_order_line_id.product_uom_qty:
                available_qty = line.sale_order_line_id.product_uom_qty - other_lines_qty
                raise ValidationError(_(
                    "La quantité totale dispatchée (%(total)s) ne peut pas dépasser "
                    "la quantité commandée (%(ordered)s) pour le produit %(product)s.\n"
                    "Quantité encore disponible : %(available)s",
                    total=total_qty,
                    ordered=line.sale_order_line_id.product_uom_qty,
                    available=max(0, available_qty),
                    product=line.product_id.display_name
                ))