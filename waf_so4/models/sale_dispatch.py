from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class SaleDispatch(models.Model):
    _name = 'sale.dispatch'
    _description = 'Sale Dispatch'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'
    _sql_constraints = [
        ('unique_sale_order_dispatch', 
         'UNIQUE(sale_order_id)',
         'Un dispatch existe déjà pour cette commande. Une commande ne peut avoir qu\'un seul dispatch.')
    ]

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        depends=['sale_order_id.currency_id'],
        store=True,
        string='Currency'
    )

    current_dispatch_progress = fields.Float(
        string='Current Dispatch Progress',
        compute='_compute_current_dispatch_progress',
        store=True,
        help="Percentage of quantities in this dispatch"
    )

    global_dispatch_progress = fields.Float(
        string='Global Dispatch Progress',
        compute='_compute_global_dispatch_progress',
        store=True,
        help="Global percentage of dispatched quantities across all dispatches",
        digits=(5, 2)
    )

    line_ids = fields.One2many(
        'sale.line.dispatch',
        'dispatch_id',
        string='Dispatch Lines'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='sale_order_id.company_id',
        store=True
    )

    picking_ids = fields.Many2many(
        'stock.picking',
        string='Delivery Orders',
        copy=False,
        readonly=True
    )

    picking_count = fields.Integer(
        string='Delivery Orders Count',
        compute='_compute_picking_count'
    )

    mandator_id = fields.Many2one(
        'res.partner',
        string='Mandator',
        required=True
    )

    commitment_date = fields.Datetime(
        string='Commitment Date',
        tracking=True,
        help="This is the delivery date promised to the customer"
    )

    dispatch_progress = fields.Float(
        string='Progress',
        compute='_compute_dispatch_progress',
        store=True,
        help="Percentage of delivered quantities based on stock moves"
    )

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Default Shipping Address',
        help="Default shipping address for this dispatch. Can be overridden at line level."
    )

    product_id = fields.Many2one('product.product', string='Product')
    product_uom_qty = fields.Float(string='Quantity')
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    stakeholder_id = fields.Many2one('res.partner', string='Stakeholder')
    scheduled_date = fields.Date(string='Scheduled Date')

    stakeholder_ids = fields.Many2many(
        'res.partner',
        'sale_dispatch_stakeholder_rel',
        'dispatch_id',
        'mandator_id',
        string='Stakeholders',
        domain="[('is_company', '=', True)]",
        help="Liste des partenaires concernés par ce dispatch",
        copy=True,
        required=True
    )

    stakeholder_count = fields.Integer(
        string='Stakeholder Count',
        compute='_compute_stakeholder_count',
        store=True
    )

    note = fields.Text(
        string='Notes',
        help="Notes internes pour ce dispatch"
    )

    draft_line_count = fields.Integer(
        string='Draft Lines Count',
        compute='_compute_line_counts',
        store=True
    )

    confirmed_line_count = fields.Integer(
        string='Confirmed Lines Count',
        compute='_compute_line_counts',
        store=True
    )

    picking_state = fields.Selection([
        ('waiting', 'En attente'),
        ('assigned', 'Réservé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État des BL',
       compute='_compute_picking_state',
       store=True)

    @api.depends('picking_ids', 'picking_ids.state')
    def _compute_state(self):
        for dispatch in self:
            if not dispatch.line_ids:
                dispatch.state = 'draft'
            elif all(line.state == 'done' for line in dispatch.line_ids):
                dispatch.state = 'done'
            elif all(line.state == 'cancel' for line in dispatch.line_ids):
                dispatch.state = 'cancel'
            elif any(line.state == 'confirmed' for line in dispatch.line_ids):
                dispatch.state = 'confirmed'
            else:
                dispatch.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.dispatch') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        """Confirme le dispatch en passant en revue chaque ligne."""
        for dispatch in self:
            # Parcourir chaque ligne individuellement
            for line in dispatch.line_ids:
                if line.state == 'draft':
                    try:
                        line.write({'state': 'confirmed'})
                        _logger.info(
                            f"Line {line.display_name} confirmed in dispatch {dispatch.name}"
                        )
                    except Exception as e:
                        _logger.error(
                            f"Error confirming line {line.display_name} in dispatch {dispatch.name}: {str(e)}"
                        )
                        raise ValidationError(_(
                            "Erreur lors de la confirmation de la ligne %(line)s: %(error)s",
                            line=line.display_name,
                            error=str(e)
                        ))
            
            # Vérifier si toutes les lignes sont dans un état final pour confirmer le dispatch
            if all(line.state in ['confirmed', 'done', 'cancel'] for line in dispatch.line_ids):
                dispatch.write({'state': 'confirmed'})
                _logger.info(f"Dispatch {dispatch.name} confirmed")

        return True

    def action_create_pickings(self):
        """Crée les bons de livraison pour les lignes confirmées."""
        for dispatch in self:
            if dispatch.state != 'confirmed':
                raise ValidationError(_(
                    "Le dispatch doit être confirmé pour créer les bons de livraison."
                ))

            # Grouper les lignes par stakeholder et adresse de livraison
            lines_by_delivery = {}
            for line in dispatch.line_ids.filtered(lambda l: l.state == 'confirmed'):
                key = (line.stakeholder_id.id, line.partner_shipping_id.id)
                if key not in lines_by_delivery:
                    lines_by_delivery[key] = []
                lines_by_delivery[key].append(line)

            # Récupérer le type d'opération pour les livraisons
            picking_type_out = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('warehouse_id.company_id', '=', dispatch.company_id.id)
            ], limit=1)

            if not picking_type_out:
                raise ValidationError(_(
                    "Aucun type d'opération de sortie n'a été trouvé pour la société %(company)s",
                    company=dispatch.company_id.name
                ))

            # Créer un BL par groupe
            for (stakeholder_id, shipping_id), lines in lines_by_delivery.items():
                # Récupérer le partenaire d'expédition
                shipping_partner = self.env['res.partner'].browse(shipping_id)
                
                # S'assurer que la date est un datetime
                scheduled_date = lines[0].scheduled_date
                if not scheduled_date:
                    scheduled_date = fields.Datetime.now()
                
                # Créer l'en-tête du BL
                picking_vals = {
                    'partner_id': shipping_id,  # Adresse de livraison
                    'stakeholder_id': stakeholder_id,  # Stakeholder
                    'picking_type_id': picking_type_out.id,
                    'location_id': picking_type_out.default_location_src_id.id,
                    'location_dest_id': picking_type_out.default_location_dest_id.id,
                    'scheduled_date': scheduled_date,
                    'origin': dispatch.name,
                    'company_id': dispatch.company_id.id,
                    'mandator_id': dispatch.mandator_id.id,
                    'dispatch_id': dispatch.id,  # Lien vers le dispatch
                    'delivery_site_name': shipping_partner.name,
                    'delivery_street': shipping_partner.street,
                    'delivery_street2': shipping_partner.street2,
                    'delivery_city': shipping_partner.city,
                    'delivery_zip': shipping_partner.zip,
                    'partner_shipping_id': shipping_id,  # Adresse de livraison
                    'stakeholder_id': stakeholder_id  # Stakeholder
                }

                # Vérifier que les emplacements sont bien définis
                if not picking_vals['location_id'] or not picking_vals['location_dest_id']:
                    warehouse = picking_type_out.warehouse_id
                    if not picking_vals['location_id']:
                        picking_vals['location_id'] = warehouse.lot_stock_id.id
                    if not picking_vals['location_dest_id']:
                        picking_vals['location_dest_id'] = warehouse.wh_output_stock_loc_id.id

                # Créer le BL
                picking = self.env['stock.picking'].create(picking_vals)

                # Créer les mouvements de stock avec la date planifiée
                for line in lines:
                    move_vals = {
                        'name': line.sale_order_line_id.name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'picking_id': picking.id,
                        'location_id': picking.location_id.id,
                        'location_dest_id': picking.location_dest_id.id,
                        'sale_line_id': line.sale_order_line_id.id,
                        'company_id': dispatch.company_id.id,
                        'date': scheduled_date,  # Ajout de la date planifiée
                    }
                    move = self.env['stock.move'].create(move_vals)
                    
                    # Lier le BL à la ligne de dispatch et marquer comme terminé
                    line.write({
                        'picking_id': picking.id,
                        'state': 'done'
                    })

                # Forcer la mise à jour de la date planifiée
                picking._set_scheduled_date()

                # Ajouter le BL aux pickings du dispatch
                dispatch.write({
                    'picking_ids': [(4, picking.id)]
                })

                # Confirmer le BL
                picking.action_confirm()

            # Si toutes les lignes ont un BL créé, marquer le dispatch comme terminé
            if all(line.state in ['done', 'cancel'] for line in dispatch.line_ids):
                dispatch.write({'state': 'done'})

            _logger.info(f"Created delivery orders for dispatch {dispatch.name}")
        return True

    @api.constrains('state', 'sale_order_id')
    def _check_confirmation_requirements(self):
        """Vérifie que le dispatch ne peut être confirmé que si la commande est confirmée."""
        for dispatch in self:
            if dispatch.state == 'confirmed' and dispatch.sale_order_id.state not in ['sale', 'done']:
                raise ValidationError(_("Un dispatch ne peut être confirmé que si la commande liée est confirmée."))

    def action_done(self):
        """Marque le dispatch comme terminé."""
        for dispatch in self:
            if all(line.state in ['done', 'cancel'] for line in dispatch.line_ids):
                # Marquer comme terminé uniquement si toutes les lignes sont terminées ou annulées
                dispatch.write({'state': 'done'})
            else:
                raise ValidationError(_("Toutes les lignes doivent être terminées ou annulées pour marquer le dispatch comme terminé."))
            return True

    def action_cancel(self):
        """Annule le dispatch et ses lignes."""
        for dispatch in self:
            if dispatch.state not in ['done', 'cancel']:
                # Annuler toutes les lignes non terminées
                active_lines = dispatch.line_ids.filtered(lambda l: l.state not in ['done', 'cancel'])
                if active_lines:
                    active_lines.write({'state': 'cancel'})
            dispatch.write({'state': 'cancel'})
        return True

    def action_set_to_draft(self):
        """Remet le dispatch et ses lignes en brouillon."""
        for dispatch in self:
            if dispatch.state == 'cancel':
                # Remettre en brouillon toutes les lignes annulées
                cancelled_lines = dispatch.line_ids.filtered(lambda l: l.state == 'cancel')
                if cancelled_lines:
                    cancelled_lines.write({'state': 'draft'})
            dispatch.write({'state': 'draft'})
        return True

    def action_view_pickings(self):
        """Display associated delivery orders."""
        self.ensure_one()
        return {
            'name': _('Delivery Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'context': {'create': False},
        }

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for dispatch in self:
            dispatch.picking_count = len(dispatch.picking_ids)

    @api.constrains('sale_order_id')
    def _check_sale_order(self):
        """Check if the order is linked to dispatch delivery mode."""
        for dispatch in self:
            if dispatch.sale_order_id.delivery_mode != 'dispatch':
                raise ValidationError(_(
                    "The order must be configured for dispatch delivery mode."
                ))

    @api.constrains('line_ids')
    def _check_lines(self):
        """Check if there is at least one dispatch line."""
        for dispatch in self:
            if not dispatch.line_ids:
                raise ValidationError(_("A dispatch must have at least one line."))

    def _convert_qty_uom(self, qty, from_uom, to_uom):
        """Convertit une quantité d'une unité de mesure à une autre."""
        if not from_uom or not to_uom:
            return qty
        if from_uom == to_uom:
            return qty
        return from_uom._compute_quantity(qty, to_uom)

    @api.depends('line_ids.product_uom_qty', 'sale_order_id.order_line.product_uom_qty')
    def _compute_current_dispatch_progress(self):
        for dispatch in self:
            total_qty = sum(line.product_uom_qty for line in dispatch.sale_order_id.order_line)
            if not total_qty:
                dispatch.current_dispatch_progress = 0.0
                continue

            dispatched_qty = sum(
                dispatch._convert_qty_uom(
                    line.product_uom_qty,
                    line.product_uom,
                    line.sale_order_line_id.product_uom
                )
                for line in dispatch.line_ids.filtered(lambda l: l.state != 'cancel')
            )
            dispatch.current_dispatch_progress = min(100.0, (dispatched_qty / total_qty) * 100)

    @api.onchange('sale_order_id')
    def _onchange_sale_order(self):
        """Met à jour les stakeholders depuis la commande."""
        if self.sale_order_id:
            self.stakeholder_ids = [(6, 0, self.sale_order_id.stakeholder_ids.ids)]

    @api.constrains('stakeholder_ids')
    def _check_stakeholders(self):
        """Vérifie qu'il y a au moins un partenaire concerné."""
        for dispatch in self:
            if not dispatch.stakeholder_ids:
                raise ValidationError(_("Un dispatch doit avoir au moins un partenaire concerné."))

    def write(self, vals):
        """Override write method"""
        res = super().write(vals)

        # Synchronisation des stakeholders avec la commande
        if 'stakeholder_ids' in vals:
            for dispatch in self:
                if dispatch.sale_order_id and not self.env.context.get('skip_order_sync'):
                    dispatch.sale_order_id.with_context(skip_dispatch_sync=True).write({
                        'stakeholder_ids': vals['stakeholder_ids']
                    })

        # Synchronisation de la date d'engagement
        if 'commitment_date' in vals:
            for record in self:
                record.sale_order_id.write({
                    'commitment_date': vals['commitment_date']
                })

        return res

    @api.constrains('line_ids', 'sale_order_id')
    def _check_total_dispatch_quantity(self):
        for dispatch in self:
            # Group lines by order line
            lines_by_order_line = {}
            for line in dispatch.line_ids:
                if line.state != 'cancel':
                    if line.sale_order_line_id not in lines_by_order_line:
                        lines_by_order_line[line.sale_order_line_id] = 0
                    lines_by_order_line[line.sale_order_line_id] += line.product_uom_qty

            # Check each order line
            for order_line, total_qty in lines_by_order_line.items():
                if total_qty > order_line.product_uom_qty:
                    raise ValidationError(_(
                        "Total dispatched quantity (%(dispatched)s) cannot exceed "
                        "ordered quantity (%(ordered)s) for product %(product)s.",
                        dispatched=total_qty,
                        ordered=order_line.product_uom_qty,
                        product=order_line.product_id.display_name
                    ))

    @api.constrains('stakeholder_id')
    def _check_partner_shipping(self):
        return True

    @api.depends('sale_order_id.order_line.dispatched_qty_line', 'sale_order_id.order_line.product_uom_qty')
    def _compute_global_dispatch_progress(self):
        for dispatch in self:
            dispatch.global_dispatch_progress = dispatch.sale_order_id.dispatch_percent_global

    def action_create_delivery(self):
        """Crée les bons de livraison groupés par date/stakeholder."""
        self.ensure_one()
        
        # 1. Récupérer les lignes confirmées
        lines = self.line_ids.filtered(lambda l: l.state == 'confirmed')
        if not lines:
            raise UserError(_("No confirmed lines to deliver."))

        # ... reste du code de action_create_delivery ...

    def _prepare_picking_values(self, scheduled_date, lines):
        """Prépare les valeurs pour la création du bon de livraison groupé."""
        # ... code de _prepare_picking_values ...

    def unlink(self):
        """Empêche la suppression d'un dispatch lié à une commande."""
        for dispatch in self:
            if dispatch.sale_order_id:
                raise UserError(_(
                    "Vous ne pouvez pas supprimer un dispatch lié à une commande. "
                    "Utilisez plutôt l'action 'Annuler' si nécessaire."
                ))
        return super().unlink()

    @api.depends('stakeholder_ids')
    def _compute_stakeholder_count(self):
        for dispatch in self:
            dispatch.stakeholder_count = len(dispatch.stakeholder_ids)

    def action_view_stakeholders(self):
        """Display associated stakeholders."""
        self.ensure_one()
        return {
            'name': _('Stakeholders'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.stakeholder_ids.ids)],
            'context': {'create': False},
        }

    @api.depends('line_ids.state')
    def _compute_line_counts(self):
        """Calcule le nombre de lignes dans chaque état."""
        for dispatch in self:
            dispatch.draft_line_count = len(dispatch.line_ids.filtered(lambda l: l.state == 'draft'))
            dispatch.confirmed_line_count = len(dispatch.line_ids.filtered(lambda l: l.state == 'confirmed'))

    @api.depends('line_ids.state')
    def _compute_picking_state(self):
        """Calcule l'état global des BL du dispatch."""
        for dispatch in self:
            pickings = dispatch.mapped('line_ids.picking_id')
            if not pickings:
                dispatch.picking_state = False
            elif all(p.state == 'done' for p in pickings):
                dispatch.picking_state = 'done'
            elif all(p.state == 'cancel' for p in pickings):
                dispatch.picking_state = 'cancel'
            elif any(p.state == 'assigned' for p in pickings):
                dispatch.picking_state = 'assigned'
            else:
                dispatch.picking_state = 'waiting'