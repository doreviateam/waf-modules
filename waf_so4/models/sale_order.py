from odoo import api, fields, models, _
import logging
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'portal.mixin']
    _description = 'Sales Order with Dispatch'

    # ------------------
    # Fields Definition
    # ------------------
    # Portal related fields
    transaction_ids = fields.Many2many(
        'payment.transaction',
        'sale_order_dispatch_transaction_rel',
        'sale_order_id',
        'transaction_id',
        string='Transactions',
        copy=False,
        readonly=True
    )

    tag_ids = fields.Many2many(
        'crm.tag',
        'sale_order_dispatch_tag_rel',
        'sale_order_id',
        'tag_id',
        string='Tags'
    )

    # Dispatch related fields
    delivery_mode = fields.Selection([
        ('standard', 'Standard'),
        ('dispatch', 'Dispatch')
    ], string='Delivery Mode', default='standard', index=True)

    stakeholder_ids = fields.Many2many(
        'res.partner',
        'sale_order_stakeholder_rel',
        'order_id',
        'partner_id',
        string='Stakeholders',
        domain="[('is_company', '=', True)]",
        help="Liste des partenaires concernés par cette commande en mode dispatch",
        copy=True
    )

    dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Dispatch',
        copy=False,
        readonly=True,
        index=True
    )

    active_dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Current Dispatch',
        related='dispatch_id',
        readonly=True,
        store=True,
        index=True
    )

    # Computed fields
    dispatch_percent_global = fields.Float(
        string='Global Dispatch Progress',
        compute='_compute_dispatch_percent_global',
        store=True,
        help="Global percentage of dispatched quantities",
        digits=(5, 2)
    )

    picking_count_from_dispatch = fields.Integer(
        string='Delivery Orders from Dispatch',
        compute='_compute_picking_count_from_dispatch'
    )

    dispatch_line_count = fields.Integer(
        string='Dispatch Lines Count',
        compute='_compute_dispatch_line_count'
    )

    # ------------------------
    # Compute and Constraints
    # ------------------------
    def _compute_access_url(self):
        """Calcule l'URL d'accès au portail pour chaque commande"""
        super()._compute_access_url()
        for order in self:
            order.access_url = '/my/orders/%s' % order.id

    @api.depends('order_line.dispatched_qty_line', 'order_line.product_uom_qty')
    def _compute_dispatch_percent_global(self):
        """Calcule le pourcentage global de dispatch pour la commande"""
        for order in self:
            total_qty = sum(line.product_uom_qty for line in order.order_line)
            dispatched_qty = sum(line.dispatched_qty_line for line in order.order_line)
            order.dispatch_percent_global = min(100.0, (dispatched_qty / total_qty) * 100) if total_qty else 0.0

    @api.depends('dispatch_id.picking_ids')
    def _compute_picking_count_from_dispatch(self):
        """Calcule le nombre de bons de livraison liés au dispatch"""
        for order in self:
            order.picking_count_from_dispatch = len(order.dispatch_id.picking_ids if order.dispatch_id else [])

    @api.depends('dispatch_id.line_ids')
    def _compute_dispatch_line_count(self):
        """Calcule le nombre de lignes de dispatch"""
        for order in self:
            order.dispatch_line_count = len(order.dispatch_id.line_ids if order.dispatch_id else [])

    @api.constrains('stakeholder_ids', 'delivery_mode')
    def _check_dispatch_requirements(self):
        """Vérifie que les stakeholders ne sont définis qu'en mode dispatch"""
        for order in self:
            if order.stakeholder_ids and order.delivery_mode != 'dispatch':
                raise ValidationError(_("Les partenaires concernés ne peuvent être définis qu'en mode dispatch."))

    @api.constrains('delivery_mode', 'stakeholder_ids')
    def _check_stakeholders(self):
        """Vérifie la cohérence des stakeholders selon le mode de livraison"""
        for order in self:
            if order.delivery_mode == 'dispatch' and not order.stakeholder_ids:
                raise UserError(_("En mode dispatch, vous devez définir au moins un partenaire concerné."))
            elif order.delivery_mode == 'standard' and order.stakeholder_ids:
                raise UserError(_("Les partenaires concernés ne peuvent être définis qu'en mode dispatch."))

    @api.constrains('dispatch_id')
    def _check_single_dispatch(self):
        """S'assure qu'il n'y a qu'un seul dispatch par commande"""
        for order in self:
            if len(order.dispatch_id) > 1:
                raise ValidationError(_("Une commande ne peut avoir qu'un seul dispatch."))

    # ------------------------
    # Onchange Methods
    # ------------------------
    @api.onchange('delivery_mode')
    def _onchange_delivery_mode(self):
        """Gère le changement de mode de livraison"""
        if self.delivery_mode == 'standard':
            self.stakeholder_ids = False
        elif self.delivery_mode == 'dispatch' and self.partner_id and not self.stakeholder_ids:
                self.stakeholder_ids = [(4, self.partner_id.id)]

    @api.onchange('partner_id')
    def _onchange_partner_id_shipping(self):
        """Définit l'adresse de livraison par défaut du client"""
        if self.partner_id and self.partner_id.default_shipping_address_id:
            self.partner_shipping_id = self.partner_id.default_shipping_address_id.delivery_contact_id

    # ------------------------
    # CRUD Methods
    # ------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Hérite la création pour définir l'adresse de livraison par défaut"""
        for vals in vals_list:
            if vals.get('partner_id') and not vals.get('partner_shipping_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.default_shipping_address_id:
                    vals['partner_shipping_id'] = partner.default_shipping_address_id.delivery_contact_id.id

        return super().create(vals_list)

    def write(self, vals):
        """Override write method"""
        if 'delivery_mode' in vals and self.state not in ['draft', 'sent']:
            raise UserError(_("Le mode de livraison ne peut pas être modifié après la confirmation de la commande."))

        res = super().write(vals)

        # Synchronisation des stakeholders avec le dispatch
        if 'stakeholder_ids' in vals:
            for order in self:
                if order.dispatch_id and not self.env.context.get('skip_dispatch_sync'):
                    order.dispatch_id.with_context(skip_order_sync=True).write({
                        'stakeholder_ids': vals['stakeholder_ids']
                    })

        if 'delivery_mode' in vals and vals['delivery_mode'] == 'standard':
            self.stakeholder_ids = False

        return res

    # ------------------------
    # Business Methods
    # ------------------------
    def action_confirm(self):
        """Override order confirmation"""
        res = super().action_confirm()

        for order in self:
            if order.delivery_mode == 'dispatch':
                order.picking_ids.sudo().unlink()

                if not order.dispatch_id:
                    # Chercher un dispatch existant
                    existing_dispatch = self.env['sale.dispatch'].search([
                        ('sale_order_id', '=', order.id),
                        ('state', '!=', 'cancel')
                    ], limit=1)
                    
                    if existing_dispatch:
                        order.dispatch_id = existing_dispatch.id
                    else:
                        # Créer un nouveau dispatch seulement si aucun n'existe
                        dispatch = self.env['sale.dispatch'].create({
                            'sale_order_id': order.id,
                            'mandator_id': order.partner_id.id,
                            'stakeholder_ids': [(6, 0, order.stakeholder_ids.ids)],
                            'commitment_date': order.commitment_date,
                        })
                        order.dispatch_id = dispatch.id

        return res

    def _create_delivery(self):
        """Handle delivery creation in both modes"""
        return super()._create_delivery()

    # ------------------------
    # Action Methods
    # ------------------------
    def action_show_dispatch(self):
        """Display or create the dispatch"""
        self.ensure_one()
        
        DispatchModel = self.env['sale.dispatch']
        dispatch = DispatchModel.search([
            ('sale_order_id', '=', self.id),
            ('state', '!=', 'cancel')  # On ne prend que les dispatches non annulés
        ], limit=1)
        
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.dispatch',
            'view_mode': 'form',
            'name': _('Show Dispatch') if dispatch else _('Create Dispatch'),
            'res_id': dispatch.id if dispatch else False,
            'context': {
                'form_view_initial_mode': 'edit' if dispatch else 'create',
                'default_sale_order_id': self.id,
                'default_mandator_id': self.partner_id.id,
                'default_stakeholder_ids': [(6, 0, self.stakeholder_ids.ids)],
            },
        }
        
        return action

    def action_add_dispatch(self):
        """Open the current dispatch"""
        self.ensure_one()
        return self.action_show_dispatch()

    def action_view_dispatch_pickings(self):
        """Display delivery orders linked to dispatch"""
        self.ensure_one()
        if not self.dispatch_id:
            return

        pickings = self.dispatch_id.picking_ids
        action = {
            'name': _('Dispatch Delivery Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', pickings.ids)],
        }
        if len(pickings) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': pickings.id,
            })
        return action

    def action_view_dispatch_lines(self):
        """Display dispatch lines"""
        self.ensure_one()
        if not self.dispatch_id:
            return

        return {
            'name': _('Dispatch Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.line.dispatch',
            'view_mode': 'tree,form',
            'domain': [('dispatch_id', '=', self.dispatch_id.id)],
        }

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    dispatched_qty_line = fields.Float(
        string='Quantité Dispatchée',
        compute='_compute_dispatched_qty_line',
        store=True,
        help="Quantité totale dispatchée pour cette ligne de commande"
    )

    remaining_qty_line = fields.Float(
        string='Quantité Restante',
        compute='_compute_remaining_qty_line',
        store=True,
        help="Quantité restante à dispatcher"
    )

    @api.depends('dispatch_line_ids.product_uom_qty', 'dispatch_line_ids.state', 'product_uom_qty')
    def _compute_dispatched_qty_line(self):
        for line in self:
            dispatched_qty = 0.0
            dispatch_lines = self.env['sale.line.dispatch'].search([
                ('sale_order_line_id', '=', line.id),
                ('state', 'not in', ['cancel'])
            ])
            
            for dispatch_line in dispatch_lines:
                dispatched_qty += dispatch_line._convert_qty_uom(
                    dispatch_line.product_uom_qty,
                    dispatch_line.product_uom,
                    line.product_uom
                )
            line.dispatched_qty_line = dispatched_qty

    @api.depends('product_uom_qty', 'dispatched_qty_line')
    def _compute_remaining_qty_line(self):
        for line in self:
            line.remaining_qty_line = max(0.0, line.product_uom_qty - line.dispatched_qty_line)

