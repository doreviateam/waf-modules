from odoo import api, fields, models, _
import logging
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'portal.mixin']
    _description = 'Sales Order with Dispatch'

    def _compute_access_url(self):
        super()._compute_access_url()
        for order in self:
            order.access_url = '/my/orders/%s' % order.id

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

    delivery_mode = fields.Selection([
        ('standard', 'Standard'),
        ('dispatch', 'Dispatch')
    ], string='Delivery Mode', default='standard')

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
        readonly=True
    )

    active_dispatch_id = fields.Many2one(
        'sale.dispatch',
        string='Current Dispatch',
        related='dispatch_id',
        readonly=True
    )

    dispatch_percent = fields.Float(
        string='Dispatch Progress',
        compute='_compute_dispatch_percent',
        store=True,
        help="Percentage of dispatched quantities"
    )

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

    # quand on change delivery_mode, stackholder_ids est vide
    @api.onchange('delivery_mode')
    def _onchange_delivery_mode(self):
        """Gère le changement de mode de livraison"""
        if self.delivery_mode == 'standard':
            self.stakeholder_ids = False
        elif self.delivery_mode == 'dispatch' and self.partner_id:
            # Ajoute automatiquement le client comme stakeholder s'il n'y en a pas encore
            if not self.stakeholder_ids:
                self.stakeholder_ids = [(4, self.partner_id.id)]

    @api.constrains('stakeholder_ids', 'delivery_mode')
    def _check_dispatch_requirements(self):
        """Check that stakeholders are only set in dispatch mode."""
        for order in self:
            if order.stakeholder_ids and order.delivery_mode != 'dispatch':
                raise ValidationError(_("Les partenaires concernés ne peuvent être définis qu'en mode dispatch."))
    

    def action_confirm(self):
        """Override order confirmation."""
        # Les vérifications des stakeholders et des lignes sont déjà gérées par _check_dispatch_requirements
        
        # Laisser le processus standard se dérouler
        res = super().action_confirm()

        # Traitement post-confirmation pour les commandes en mode dispatch
        for order in self:
            if order.delivery_mode == 'dispatch':
                # Supprimer les pickings créés car on les recrée à la confirmation du dispatch
                order.picking_ids.sudo().unlink()
                
                # Créer le dispatch s'il n'existe pas déjà
                if not order.dispatch_id:
                    dispatch = self.env['sale.dispatch'].create({
                        'sale_order_id': order.id,
                        'mandator_id': order.partner_id.id,
                        'stakeholder_ids': [(6, 0, order.stakeholder_ids.ids)],
                        'commitment_date': order.commitment_date,
                    })
                    order.dispatch_id = dispatch.id

        return res

    def write(self, vals):
        """Override write method."""
        res = super().write(vals)
        if 'delivery_mode' in vals:
            for order in self:
                if order.state not in ['draft', 'sent']:
                    raise UserError(_("Le mode de livraison ne peut pas être modifié après la confirmation de la commande."))
                if vals['delivery_mode'] == 'standard':
                    order.stakeholder_ids = False
        return res

    def _create_delivery(self):
        """Handle delivery creation in both modes."""
        # Toujours créer les livraisons, même en mode dispatch
        return super()._create_delivery()

    def action_show_dispatch(self):
        """Display or create the dispatch."""
        self.ensure_one()
        if not self.dispatch_id:
            return {
                'name': _('Create Dispatch'),
                'view_mode': 'form',
                'res_model': 'sale.dispatch',
                'type': 'ir.actions.act_window',
                'context': {
                    'default_sale_order_id': self.id,
                    'default_mandator_id': self.partner_id.id,
                    'default_stakeholder_ids': [(6, 0, self.stakeholder_ids.ids)],
                },
            }
        # 03 20 49 58 87 
            
        return {
            'name': _('Show Dispatch'),
            'view_mode': 'form',
            'res_model': 'sale.dispatch',
            'type': 'ir.actions.act_window',    
            'res_id': self.dispatch_id.id,
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_add_dispatch(self):
        """Open the current dispatch."""
        self.ensure_one()
        return self.action_show_dispatch()

    @api.depends('order_line.dispatched_qty', 'order_line.product_uom_qty')
    def _compute_dispatch_percent(self):
        for order in self:
            if not order.order_line:
                order.dispatch_percent = 0.0
                continue

            total_qty = sum(order.order_line.mapped('product_uom_qty'))
            if not total_qty:
                order.dispatch_percent = 0.0
                continue

            dispatched_qty = sum(order.order_line.mapped('dispatched_qty'))
            order.dispatch_percent = min(100.0, (dispatched_qty / total_qty) * 100)

    @api.depends('dispatch_id', 'dispatch_id.state')
    def _compute_active_dispatch(self):
        """Le dispatch actif est le seul dispatch de la commande."""
        for order in self:
            order.active_dispatch_id = order.dispatch_id

    @api.depends('order_line.dispatched_qty', 'order_line.product_uom_qty')
    def _compute_dispatch_percent_global(self):
        for order in self:
            if not order.order_line:
                order.dispatch_percent_global = 0.0
                continue

            total_qty = sum(order.order_line.mapped('product_uom_qty'))
            if not total_qty:
                order.dispatch_percent_global = 0.0
                continue

            dispatched_qty = sum(order.order_line.mapped('dispatched_qty'))
            order.dispatch_percent_global = min(100.0, (dispatched_qty / total_qty) * 100)

    @api.depends('dispatch_id.picking_ids')
    def _compute_picking_count_from_dispatch(self):
        for order in self:
            order.picking_count_from_dispatch = len(order.dispatch_id.picking_ids if order.dispatch_id else [])

    def action_view_dispatch_pickings(self):
        """Display delivery orders linked to dispatch."""
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

    @api.depends('dispatch_id.line_ids')
    def _compute_dispatch_line_count(self):
        for order in self:
            order.dispatch_line_count = len(order.dispatch_id.line_ids if order.dispatch_id else [])

    def action_view_dispatch_lines(self):
        """Display dispatch lines."""
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

    @api.onchange('partner_id')
    def _onchange_partner_id_shipping(self):
        """Définit l'adresse de livraison par défaut du client"""
        if self.partner_id and self.partner_id.default_shipping_address_id:
            # Récupérer le contact de livraison lié à l'adresse par défaut
            self.partner_shipping_id = self.partner_id.default_shipping_address_id.delivery_contact_id

    @api.model_create_multi
    def create(self, vals_list):
        """Hérite la création pour définir l'adresse de livraison par défaut"""
        for vals in vals_list:
            if vals.get('partner_id') and not vals.get('partner_shipping_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.default_shipping_address_id:
                    vals['partner_shipping_id'] = partner.default_shipping_address_id.delivery_contact_id.id
        
        return super().create(vals_list)

    @api.constrains('delivery_mode', 'stakeholder_ids')
    def _check_stakeholders(self):
        """Vérifie la cohérence des stakeholders selon le mode de livraison"""
        for order in self:
            if order.delivery_mode == 'dispatch':
                if not order.stakeholder_ids:
                    raise UserError(_("En mode dispatch, vous devez définir au moins un partenaire concerné."))
            elif order.delivery_mode == 'standard' and order.stakeholder_ids:
                raise UserError(_("Les partenaires concernés ne peuvent être définis qu'en mode dispatch."))

    @api.constrains('dispatch_id')
    def _check_single_dispatch(self):
        """S'assure qu'il n'y a qu'un seul dispatch par commande."""
        for order in self:
            if len(order.dispatch_id) > 1:
                raise ValidationError(_("Une commande ne peut avoir qu'un seul dispatch."))
