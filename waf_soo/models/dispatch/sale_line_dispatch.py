from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class SaleLineDispatch(models.Model):
    _name = 'sale.line.dispatch'
    _description = 'Dispatch des lignes de commande'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'planned_date desc, id desc'

    # Champs de base avec nom calculé
    name = fields.Char(
        string='Référence',
        compute='_compute_name',
        store=True,
        tracking=True
    )
    
    @api.depends('sale_order_id.name', 'sale_order_line_id', 'stakeholder_id.name')
    def _compute_name(self):
        for record in self:
            if record.sale_order_id and record.stakeholder_id:
                sale_name = record.sale_order_id.name or ''
                line_id = record.sale_order_line_id.id or ''
                stakeholder = record.stakeholder_id.name or ''
                record.name = f"{sale_name}-L{line_id}-{stakeholder}"
            else:
                # record.name = f"{record.id}"
                record.name = "..."

    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', 
        required=True,
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        store=True
    )

    # Champs relationnels
    sale_order_id = fields.Many2one(
        'sale.order', 
        string='Commande',
        required=True,
        tracking=True,
        domain="[('state', 'not in', ['cancel'])]",
        ondelete='restrict'
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line', 
        string='Ligne de commande',
        required=True,
        tracking=True,
        domain="[('order_id', '=', sale_order_id)]",
        ondelete='restrict'
    )
    product_id = fields.Many2one(
        related='sale_order_line_id.product_id',
        store=True,
        readonly=True
    )
    product_uom = fields.Many2one(
        related='sale_order_line_id.product_uom',
        string="Unité de mesure",
        store=True
    )
    stakeholder_id = fields.Many2one(
        'res.partner',
        string='Stakeholder',
        required=True,
        tracking=True,
        domain="[('type', '!=', 'private')]",
        ondelete='restrict'
    )

    @api.onchange('stakeholder_id')
    def _onchange_stakeholder_id(self):
        """Réinitialise l'adresse de livraison quand le stakeholder change."""
        self.delivery_address_id = False
        # Retourne un domaine pour filtrer les adresses disponibles
        if self.stakeholder_id:
            return {
                'domain': {
                    'delivery_address_id': [
                        ('partner_ids', 'in', self.stakeholder_id.id),
                        ('type', '=', 'delivery'),
                        ('active', '=', True)
                    ]
                }
            }
        return {'domain': {'delivery_address_id': []}}

    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Adresse de livraison',
        required=True,
        tracking=True,
        domain="[('partner_ids', 'in', stakeholder_id), ('type', '=', 'delivery'), ('active', '=', True)]",
        ondelete='restrict'
    )
    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Bon de livraison',
        copy=False,
        readonly=True,
        tracking=True,
        ondelete='set null'
    )
    stock_move_ids = fields.One2many(
        'stock.move',
        'dispatch_id',
        string='Mouvements de stock',
        readonly=True
    )

    dispatch_group_id = fields.Many2one(
        'sale.line.dispatch.group',
        string='Groupe de dispatch',
        ondelete='cascade',
        tracking=True
    )

    line_remaining_qty = fields.Float(
        string='Quantité restante',
        compute='_compute_line_remaining_qty',
        help="Quantité restante à dispatcher sur la ligne de commande"
    )

    @api.depends('sale_order_line_id', 'sale_order_line_id.product_uom_qty')
    def _compute_line_remaining_qty(self):
        for record in self:
            if not record.sale_order_line_id:
                _logger.info("Pas de ligne de commande associée")
                record.line_remaining_qty = 0.0
                continue
            
            # Quantité totale de la ligne
            total_qty = record.sale_order_line_id.product_uom_qty
            
            # Somme des quantités des dispatches actifs (sauf annulés et terminés)
            dispatched_qty = sum(
                self.search([
                    ('sale_order_line_id', '=', record.sale_order_line_id.id),
                    ('state', 'not in', ['cancel', 'done']),
                    ('id', '!=', record.id)  # Exclut le dispatch courant
                ]).mapped('quantity')
            )
            
            # Quantité restante = total - dispatches actifs
            record.line_remaining_qty = total_qty - dispatched_qty
            
            _logger.info(
                "Calcul remaining_qty pour %s:\n"
                "- Quantité totale: %s\n"
                "- Quantité dispatchée (active): %s\n"
                "- Quantité restante: %s",
                record.sale_order_line_id.display_name,
                total_qty,
                dispatched_qty,
                record.line_remaining_qty
            )

    # Champs quantités et montants
    quantity = fields.Float(
        string='Quantité',
        required=True,
        tracking=True,
        default=1.0,
        digits='Product Unit of Measure'
    )
    unit_price = fields.Float(
        related='sale_order_line_id.price_unit',
        string='Prix unitaire',
        store=True
    )
    amount_total = fields.Monetary(
        string='Montant total',
        compute='_compute_amount_total',
        store=True,
        tracking=True
    )

    # Champs dates et états
    planned_date = fields.Date(
        string='Date planifiée',
        required=True,
        tracking=True,
        default=fields.Date.today
    )
    effective_date = fields.Date(
        string='Date effective',
        readonly=True,
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('picking', 'En livraison'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', tracking=True)

    notes = fields.Html(
        string='Notes',
        tracking=True,
        sanitize=True,
        strip_style=False
    )

    # Contraintes SQL
    _sql_constraints = [
        ('positive_quantity',
         'CHECK(quantity > 0)',
         'La quantité doit être strictement positive.')
    ]

    # Méthodes de calcul
    @api.depends('quantity', 'unit_price', 'currency_id')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = float_round(
                record.quantity * record.unit_price,
                precision_rounding=record.currency_id.rounding or 0.01
            )

    # Contraintes Python
    @api.constrains('quantity', 'sale_order_line_id')
    def _check_quantity(self):
        for record in self:
            if float_compare(
                record.quantity,
                0.0,
                precision_rounding=record.product_uom.rounding
            ) <= 0:
                raise ValidationError(_("La quantité doit être strictement positive"))
            
            if float_compare(
                record.quantity,
                record.line_remaining_qty,
                precision_rounding=record.product_uom.rounding
            ) > 0:
                raise ValidationError(_(
                    "La quantité du dispatch ne peut pas dépasser "
                    "la quantité restante disponible (%s)"
                ) % record.line_remaining_qty)

    @api.constrains('planned_date')
    def _check_planned_date(self):
        for record in self:
            if record.planned_date < fields.Date.today():
                raise ValidationError(_(
                    "La date planifiée ne peut pas être dans le passé."
                ))

    @api.onchange('dispatch_group_id')
    def _onchange_dispatch_group(self):
        if self.dispatch_group_id:
            self.stakeholder_id = self.dispatch_group_id.stakeholder_id
            self.delivery_address_id = self.dispatch_group_id.delivery_address_id
            self.planned_date = self.dispatch_group_id.planned_date

    @api.constrains('dispatch_group_id', 'stakeholder_id', 'delivery_address_id', 'planned_date')
    def _check_group_consistency(self):
        for record in self:
            if record.dispatch_group_id:
                if record.stakeholder_id != record.dispatch_group_id.stakeholder_id:
                    raise ValidationError(_("Le stakeholder doit être le même que celui du groupe de dispatch."))
                if record.delivery_address_id != record.dispatch_group_id.delivery_address_id:
                    raise ValidationError(_("L'adresse de livraison doit être la même que celle du groupe de dispatch."))
                if record.planned_date != record.dispatch_group_id.planned_date:
                    raise ValidationError(_("La date planifiée doit être la même que celle du groupe de dispatch."))

    def _prepare_stock_move_vals(self):
        self.ensure_one()
        
        # Récupération du groupe de procurement de la commande
        procurement_group = self.sale_order_line_id.order_id.procurement_group_id
        if not procurement_group:
            procurement_group = self.env['procurement.group'].create({
                'name': self.sale_order_id.name,
                'move_type': self.sale_order_id.picking_policy,
                'sale_id': self.sale_order_id.id,
                'partner_id': self.sale_order_id.partner_shipping_id.id,
            })
            self.sale_order_id.procurement_group_id = procurement_group.id

        values = {
            'name': self.name,
            'dispatch_id': self.id,
            'product_id': self.product_id.id,
            'product_uom': self.product_uom.id,
            'product_uom_qty': self.quantity,
            'date': self.planned_date,
            'location_id': self.company_id.internal_transit_location_id.id,
            'location_dest_id': self.stakeholder_id.property_stock_customer.id,
            'partner_id': self.stakeholder_id.id,
            'company_id': self.company_id.id,
            'procure_method': 'make_to_stock',
            'origin': self.name,
            'group_id': procurement_group.id,
            'sale_line_id': self.sale_order_line_id.id,
            'state': 'draft',
        }

        return values

    def _create_stock_picking(self):
        self.ensure_one()
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        vals = {
            'partner_id': self.stakeholder_id.id,
            'picking_type_id': picking_type.id,
            'location_id': self.company_id.internal_transit_location_id.id,
            'location_dest_id': self.stakeholder_id.property_stock_customer.id,
            'scheduled_date': self.planned_date,
            'origin': self.name,
            'company_id': self.company_id.id,
            'dispatch_id': self.id,
            'delivery_address_id': self.delivery_address_id.id,
        }
        picking = self.env['stock.picking'].create(vals)
        picking._update_address_from_dispatch(self)
        return picking

    # Actions
    def action_confirm(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Le dispatch doit être en état brouillon pour être confirmé."))
        
        if self.sale_order_id.delivery_mode != 'dispatch':
            raise UserError(_("Le mode de livraison doit être 'Dispatch' pour confirmer un dispatch."))
        
        _logger.info(
            "Confirmation du dispatch %s:\n"
            "- État avant: %s",
            self.name, self.state
        )
        
        self.write({
            'state': 'confirmed'
        })
        
        self.env.cr.commit()  # Force le commit de la transaction
        
        _logger.info(
            "Confirmation du dispatch %s:\n"
            "- État après: %s",
            self.name, self.state
        )
        
        return True

    def action_create_picking(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_("Le dispatch doit être confirmé pour créer un bon de livraison."))
            
        if self.sale_order_id.state != 'sale':
            raise UserError(_("La commande doit être confirmée avant de pouvoir créer un bon de livraison."))
        
        picking = self._create_stock_picking()
        move_vals = self._prepare_stock_move_vals()
        move_vals.update({'picking_id': picking.id})
        self.env['stock.move'].create(move_vals)
        
        self.write({
            'state': 'picking',
            'stock_picking_id': picking.id
        })
        return True

    def action_ship(self):
        self.ensure_one()
        if self.state != 'picking':
            raise UserError(_("Le dispatch doit avoir un bon de livraison créé avant expédition."))
        if not self.stock_picking_id.state == 'done':
            raise UserError(_("Le bon de livraison doit être validé avant l'expédition."))
        
        self.write({
            'state': 'done',
            'effective_date': fields.Date.today()
        })
        return True

    def action_done(self):
        self.ensure_one()
        if self.state != 'picking':
            raise UserError(_("Le dispatch doit être en livraison pour être terminé."))
        if not self.stock_picking_id.state == 'done':
            raise UserError(_("Le bon de livraison doit être validé pour terminer le dispatch."))
        
        self.write({
            'state': 'done',
            'effective_date': fields.Date.today()
        })
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state not in ['draft', 'confirmed']:
            raise UserError(_("Un dispatch ne peut être annulé que s'il est en brouillon ou confirmé."))
        
        _logger.info(
            "Annulation du dispatch %s:\n"
            "- État actuel: %s\n"
            "- Quantité du dispatch: %s\n"
            "- Quantité restante avant annulation: %s\n"
            "- Quantité totale de la ligne: %s",
            self.name,
            self.state,
            self.quantity,
            self.line_remaining_qty,
            self.sale_order_line_id.product_uom_qty
        )
        
        if self.stock_picking_id:
            if self.stock_picking_id.state not in ['draft', 'cancel']:
                self.stock_picking_id.action_cancel()
        
        self.write({'state': 'cancel'})
        
        return True

    def action_archive(self):
        """Archive le dispatch."""
        self.ensure_one()
        if self.state != 'cancel':
            raise UserError(_("Seuls les dispatches annulés peuvent être archivés."))
        self.write({'active': False})
        return True

    def action_draft(self):
        """Remet le dispatch au brouillon."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_("Seuls les dispatches confirmés peuvent être remis au brouillon."))
        self.write({'state': 'draft'})

    def unlink(self):
        """Surcharge de la suppression pour ne permettre la suppression que des dispatches en brouillon ou annulés."""
        if any(record.state not in ['draft', 'cancel'] for record in self):
            raise UserError(_(
                "Seuls les dispatches en brouillon ou annulés peuvent être supprimés."
            ))
        return super().unlink()

    def _sync_stock_moves(self):
        """Synchronise les mouvements de stock avec le dispatch."""
        self.ensure_one()
        if not self.stock_picking_id:
            return

        # Mise à jour des mouvements existants
        for move in self.stock_move_ids:
            if move.state not in ['done', 'cancel']:
                move.write({
                    'product_uom_qty': self.quantity,
                    'date': self.planned_date,
                })

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la création pour vérifier le mode de livraison."""
        for vals in vals_list:
            if 'sale_order_id' in vals:
                sale_order = self.env['sale.order'].browse(vals['sale_order_id'])
                if sale_order.delivery_mode != 'dispatch':
                    raise UserError(_("Impossible de créer un dispatch : le mode de livraison doit être 'Dispatch'"))
        return super().create(vals_list)

    def write(self, vals):
        """Surcharge de l'écriture pour vérifier le mode de livraison."""
        for record in self:
            if record.sale_order_id.delivery_mode != 'dispatch':
                raise UserError(_("Impossible de modifier un dispatch : le mode de livraison doit être 'Dispatch'"))
        res = super().write(vals)
        if 'quantity' in vals or 'planned_date' in vals:
            for record in self:
                record._sync_stock_moves()
        return res
