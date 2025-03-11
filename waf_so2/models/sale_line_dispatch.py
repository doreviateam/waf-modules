from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class SaleLineDispatch(models.Model):
    _name = 'sale.line.dispatch'
    _description = 'Dispatch de ligne de commande'
    _rec_name = 'sale_order_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sale_order_id desc, id desc'

    # Champs de base
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    sale_order_id = fields.Many2one('sale.order', string='Commande', required=True)
    sale_order_line_id = fields.Many2one('sale.order.line', string='Ligne de commande', required=True)
    product_id = fields.Many2one('product.product', string='Produit', required=True)
    partner_id = fields.Many2one(
        related='sale_order_id.partner_id',
        string='Client',
        store=True
    )
    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Adresse de livraison',
        required=True,
        domain="[]"  # Domaine vide par défaut
    )
    product_uom_qty = fields.Float(string='Quantité', required=True)
    product_uom = fields.Many2one(
        'uom.uom',
        string='Unité de mesure',
        related='sale_order_line_id.product_uom',
        store=True,
        readonly=True
    )
    price_unit = fields.Float(
        string='Prix unitaire',
        related='sale_order_line_id.price_unit',
        store=True,
        readonly=True
    )
    tax_id = fields.Many2many('account.tax', string='Taxes')
    discount = fields.Float(string='Remise (%)', default=0.0)
    
    # États
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('picking', 'BL Créé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', required=True, tracking=True)

    # Champs calculés
    amount_untaxed = fields.Monetary(string='Montant HT', compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary(string='Montant TTC', compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(string='Montant total', compute='_compute_amount_total', store=True)
    currency_id = fields.Many2one('res.currency', string='Devise', related='sale_order_id.currency_id', store=True)

    # Champs de stock
    picking_id = fields.Many2one('stock.picking', string='Bon de livraison', copy=False)
    move_ids = fields.One2many('stock.move', 'dispatch_id', string='Mouvements de stock')
    picking_count = fields.Integer(string='Nombre de BL', compute='_compute_picking_count')
    move_count = fields.Integer(string='Nombre de mouvements', compute='_compute_move_count')

    # Champs de dates
    commitment_date = fields.Datetime(
        string='Date promise',
        readonly=True,
        related='sale_order_id.commitment_date',
        store=True,
        help="Date de livraison promise au client dans la commande"
    )
    scheduled_date = fields.Date(
        string='Date prévue',
        required=True,
        default=lambda self: fields.Date.today()
    )

    # Ajout du champ calculé
    dispatch_progress = fields.Float(
        string='% Dispatché',
        compute='_compute_dispatch_progress',
        store=True,
        help="Pourcentage de la quantité commandée qui est dispatchée"
    )

    # Ajout des champs de regroupement
    dispatch_group_id = fields.Many2one(
        'sale.dispatch.group',
        string='Groupe de dispatch',
        readonly=True,
        help="Groupe de dispatches qui seront livrés ensemble"
    )
    grouped_with_ids = fields.Many2many(
        'sale.line.dispatch',
        string='Regroupé avec',
        compute='_compute_grouped_with',
        help="Autres dispatches qui seront livrés dans le même BL"
    )

    # Ajout du champ available_qty
    available_qty = fields.Float(
        'Quantité disponible',
        compute='_compute_available_qty',
        store=False,
        help="Quantité restante à dispatcher sur la ligne de commande"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.line.dispatch') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        """Confirme les dispatches et crée/assigne les groupes."""
        groups = self.env['sale.dispatch.group']
        
        for dispatch in self:
            # Chercher un groupe existant ou en créer un nouveau
            group = self.env['sale.dispatch.group'].search([
                ('sale_order_id', '=', dispatch.sale_order_id.id),
                ('delivery_address_id', '=', dispatch.delivery_address_id.id),
                ('scheduled_date', '=', dispatch.scheduled_date),
                ('state', '=', 'draft')
            ], limit=1)
            
            if not group:
                group = self.env['sale.dispatch.group'].create({
                    'sale_order_id': dispatch.sale_order_id.id,
                    'delivery_address_id': dispatch.delivery_address_id.id,
                    'scheduled_date': dispatch.scheduled_date,
                    'state': 'draft'
                })
                groups |= group
            
            # Assigner le dispatch au groupe
            dispatch.write({
                'dispatch_group_id': group.id,
                'state': 'confirmed'
            })
        
        return True

    def action_create_picking(self):
        """Crée le bon de livraison pour le groupe."""
        self.ensure_one()
        
        # Vérification de l'état de la commande
        if self.sale_order_id.state not in ['sale', 'done']:
            raise UserError(_("Impossible de créer un BL : la commande %s doit d'abord être confirmée.") % self.sale_order_id.name)
        
        if not self.dispatch_group_id:
            raise UserError(_("Le dispatch doit appartenir à un groupe pour créer un BL."))
        
        group = self.dispatch_group_id
        if group.picking_id:
            raise UserError(_("Un BL existe déjà pour ce groupe de dispatch."))
        
        # Création du BL pour le groupe
        picking_vals = self._prepare_picking_values()
        picking = self.env['stock.picking'].create(picking_vals)
        
        # Création des mouvements pour tous les dispatches du groupe
        for dispatch in group.dispatch_ids:
            move_vals = dispatch._prepare_move_values(picking)
            self.env['stock.move'].create(move_vals)
            dispatch.write({
                'state': 'picking',
                'picking_id': picking.id
            })
        
        # Mise à jour du groupe
        group.write({
            'picking_id': picking.id,
            'state': 'done'
        })
        
        return picking

    def action_cancel(self):
        """Annule le dispatch."""
        for dispatch in self:
            if dispatch.state == 'picking':
                raise UserError(_("Impossible d'annuler un dispatch dont le BL est déjà créé."))
            
            if dispatch.state != 'confirmed':
                raise UserError(_("Seuls les dispatches confirmés peuvent être annulés."))
            
            dispatch.write({'state': 'cancel'})
            _logger.info("Dispatch %s annulé - Quantité remise à disposition : %s", 
                        dispatch.name, dispatch.product_uom_qty)

    def _prepare_picking_values(self):
        """Prépare les valeurs pour la création du bon de livraison."""
        delivery_partner = self.env['res.partner'].create({
            'name': self.delivery_address_id.name,
            'street': self.delivery_address_id.street,
            'street2': self.delivery_address_id.street2,
            'city': self.delivery_address_id.city,
            'zip': self.delivery_address_id.zip,
            'country_id': self.delivery_address_id.country_id.id,
            'state_id': self.delivery_address_id.state_id.id,
            'phone': self.delivery_address_id.phone,
            'email': self.delivery_address_id.email,
            'type': 'delivery',
            'parent_id': self.sale_order_id.partner_id.id,
        })

        return {
            'partner_id': delivery_partner.id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'origin': f"{self.sale_order_id.name} - {self.name}",  # Référence commande + dispatch
            'scheduled_date': fields.Datetime.now() if not self.scheduled_date else fields.Datetime.from_string(f"{self.scheduled_date} 00:00:00"),
            'move_type': 'direct',
            'company_id': self.sale_order_id.company_id.id,
            'dispatch_id': self.id,
        }

    def _prepare_move_values(self, picking):
        """Prépare les valeurs pour la création du mouvement de stock."""
        return {
            'name': self.product_id.name,
            'product_id': self.product_id.id,
            'product_uom_qty': self.product_uom_qty,
            'product_uom': self.product_uom.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'dispatch_id': self.id,
            'sale_line_id': self.sale_order_line_id.id,
            'state': 'draft',
            'company_id': self.sale_order_id.company_id.id,
        }

    @api.depends('product_uom_qty', 'price_unit', 'tax_id', 'discount')
    def _compute_amounts(self):
        """Calcule les montants HT, TTC et total."""
        for dispatch in self:
            price = dispatch.price_unit * (1 - (dispatch.discount or 0.0) / 100.0)
            dispatch.amount_untaxed = dispatch.product_uom_qty * price
            taxes = dispatch.tax_id.compute_all(price, dispatch.currency_id, dispatch.product_uom_qty)
            dispatch.amount_tax = taxes['total_included'] - taxes['total_excluded']
            dispatch.amount_total = taxes['total_included']

    @api.depends('picking_id')
    def _compute_picking_count(self):
        """Calcule le nombre de bons de livraison."""
        for dispatch in self:
            dispatch.picking_count = 1 if dispatch.picking_id else 0

    @api.depends('move_ids')
    def _compute_move_count(self):
        """Calcule le nombre de mouvements de stock."""
        for dispatch in self:
            dispatch.move_count = len(dispatch.move_ids)

    @api.constrains('sale_order_line_id', 'product_uom_qty')
    def _check_quantity(self):
        for dispatch in self:
            if not dispatch.sale_order_line_id:
                continue

            total_dispatched = self.search([
                ('sale_order_line_id', '=', dispatch.sale_order_line_id.id),
                ('id', '!=', dispatch.id),
                ('state', 'not in', ['cancel'])
            ]).mapped('product_uom_qty')
            
            total_dispatched_qty = sum(total_dispatched) + dispatch.product_uom_qty
            ordered_qty = dispatch.sale_order_line_id.product_uom_qty

            if total_dispatched_qty > ordered_qty:
                raise ValidationError(_(
                    "La quantité totale dispatchée (%(dispatched)s) ne peut pas dépasser "
                    "la quantité commandée (%(ordered)s) pour le produit %(product)s"
                ) % {
                    'dispatched': total_dispatched_qty,
                    'ordered': ordered_qty,
                    'product': dispatch.product_id.name,
                })

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id(self):
        if self.sale_order_line_id:
            self.product_id = self.sale_order_line_id.product_id.id
            self.product_uom = self.sale_order_line_id.product_uom.id
            self.price_unit = self.sale_order_line_id.price_unit
            self.tax_id = self.sale_order_line_id.tax_id
            self.discount = self.sale_order_line_id.discount

            # Calculer la quantité disponible
            dispatched_qty = sum(
                d.product_uom_qty 
                for d in self.search([
                    ('sale_order_line_id', '=', self.sale_order_line_id.id),
                    ('state', 'not in', ['cancel']),
                    ('id', '!=', self._origin.id)  # Exclure l'enregistrement courant
                ])
            )
            
            available_qty = self.sale_order_line_id.product_uom_qty - dispatched_qty
            
            if available_qty <= 0:
                self.sale_order_line_id = False
                return {
                    'warning': {
                        'title': _('Ligne non disponible'),
                        'message': _('Cette ligne a déjà été entièrement dispatchée.')
                    }
                }
            
            # Définir la quantité par défaut comme la quantité disponible
            self.product_uom_qty = available_qty

            return {
                'domain': {
                    'sale_order_line_id': [
                        ('order_id', '=', self.sale_order_id.id),
                        ('product_uom_qty', '>', 0)
                    ]
                }
            }

    @api.constrains('scheduled_date')
    def _check_scheduled_date(self):
        for dispatch in self:
            if dispatch.scheduled_date < fields.Date.today():
                raise ValidationError(_("La date de livraison planifiée ne peut pas être dans le passé."))

    @api.onchange('sale_order_id')
    def _onchange_sale_order(self):
        """Met à jour la date prévue et le domaine des adresses."""
        today = fields.Date.today()
        if self.sale_order_id.commitment_date:
            commitment_date = fields.Date.to_date(self.sale_order_id.commitment_date)
            if commitment_date >= today:
                self.scheduled_date = commitment_date
            else:
                self.scheduled_date = today
        else:
            self.scheduled_date = today

        # Reset delivery_address_id when changing sale_order
        self.delivery_address_id = False

        # Return domain for delivery addresses
        domain = []
        if self.sale_order_id and self.sale_order_id.partner_id:
            domain = [
                ('partner_ids', 'in', [self.sale_order_id.partner_id.id]),
                ('type', '=', 'delivery'),
                ('active', '=', True)
            ]

        return {'domain': {'delivery_address_id': domain}}

    def name_get(self):
        """Personnalisation de l'affichage du nom"""
        result = []
        for record in self:
            name = f"{record.sale_order_id.name} - {record.product_id.name} ({record.product_uom_qty})"
            result.append((record.id, name))
        return result

    def action_view_picking(self):
        """Ouvre la vue du bon de livraison."""
        self.ensure_one()
        if not self.picking_id:
            return
        return {
            'name': _('Bon de livraison'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
        }

    @api.depends('sale_order_line_id.product_uom_qty', 'product_uom_qty')
    def _compute_dispatch_progress(self):
        for dispatch in self:
            if not dispatch.sale_order_line_id:
                dispatch.dispatch_progress = 0.0
                continue

            total_dispatched = self.search([
                ('sale_order_line_id', '=', dispatch.sale_order_line_id.id),
                ('state', 'not in', ['cancel'])
            ]).mapped('product_uom_qty')
            
            ordered_qty = dispatch.sale_order_line_id.product_uom_qty
            if ordered_qty:
                dispatch.dispatch_progress = (sum(total_dispatched) / ordered_qty) * 100
            else:
                dispatch.dispatch_progress = 0.0

    @api.depends('dispatch_group_id')
    def _compute_grouped_with(self):
        for dispatch in self:
            if dispatch.dispatch_group_id:
                dispatch.grouped_with_ids = dispatch.dispatch_group_id.dispatch_ids - dispatch
            else:
                dispatch.grouped_with_ids = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('sale_order_line_id'):
            line = self.env['sale.order.line'].browse(res['sale_order_line_id'])
            # Calculer la quantité disponible
            dispatched_qty = sum(
                d.product_uom_qty 
                for d in self.search([
                    ('sale_order_line_id', '=', line.id),
                    ('state', 'not in', ['cancel'])
                ])
            )
            available_qty = line.product_uom_qty - dispatched_qty
            if available_qty > 0:
                res['product_uom_qty'] = available_qty
        return res

    @api.depends('sale_order_line_id.product_uom_qty', 'sale_order_line_id.dispatch_ids.product_uom_qty',
                'sale_order_line_id.dispatch_ids.state')
    def _compute_available_qty(self):
        for dispatch in self:
            if dispatch.sale_order_line_id:
                total_qty = dispatch.sale_order_line_id.product_uom_qty
                
                # Somme des quantités des autres dispatches (non annulés)
                dispatched_qty = sum(
                    d.product_uom_qty 
                    for d in dispatch.sale_order_line_id.dispatch_ids 
                    if d.state != 'cancel' and d.id != dispatch._origin.id  # Exclure le dispatch courant
                )
                
                # Si le dispatch est en brouillon, on ajoute sa propre quantité à la quantité disponible
                if dispatch.state == 'draft':
                    dispatched_qty -= dispatch.product_uom_qty
                    
                dispatch.available_qty = total_qty - dispatched_qty
            else:
                dispatch.available_qty = 0.0