from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR


class PreSaleOrderLine(models.Model):
    _name = 'pre.sale.order.line'
    _description = 'Ligne de préparation de commande'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'delivery_date'


    product_id = fields.Many2one('product.product', string='Product')
    is_preso = fields.Boolean(string='Is Preso', default=False)
    confirm_dispatch = fields.Boolean(string='Confirm Dispatch', default=False)
    

    sale_order_id = fields.Many2one('sale.order', string='Commande', required=True)
    sale_order_line_id = fields.Many2one('sale.order.line', string='Ligne de commande', ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='sale_order_id.partner_id',
        store=True,
        readonly=True
    )
    delivery_address_id = fields.Many2one(
        'res.partner',
        string='Adresse de livraison',
        required=True,
        domain="[('parent_id', '=', partner_id)]"
    )
    product_id = fields.Many2one('product.product', string='Produit', required=True, tracking=True)
    quantity = fields.Float(string='Quantité', required=True, digits='Product Unit of Measure', tracking=True)
    quantity_delivered = fields.Float(string='Quantité livrée', compute='_compute_quantities', store=True)
    quantity_remaining = fields.Float(string='Reste à livrer', compute='_compute_quantities', store=True)
    quantity_planned = fields.Float(string='Quantité planifiée', compute='_compute_quantities', store=True)
    unit_price = fields.Float(string='Prix unitaire', related='product_id.list_price', readonly=True, store=True)
    uom_id = fields.Many2one(related='product_id.uom_id', readonly=True)
    company_id = fields.Many2one('res.company', string='Société', required=True, 
                                default=lambda self: self.env.company)
    delivery_ids = fields.One2many('pre.sale.order.line.delivery', 'preso_line_id', string='Livraisons')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', required=True, tracking=True)


    @api.model
    def _default_delivery_date(self):
        """Retourne le troisième jour ouvré à 17h à partir d'aujourd'hui"""
        today = fields.Date.today()
        current_date = fields.Datetime.now()
        
        # Si on est après 17h, on commence à compter à partir de demain
        if current_date.time() > time(17, 0):
            today += relativedelta(days=1)

        business_days = 0
        target_date = today
        while business_days < 3:
            target_date += relativedelta(days=1)
            if target_date.weekday() < 5:  # 0-4 = Lundi-Vendredi
                business_days += 1

        return datetime.combine(target_date, time(17, 0))


    delivery_date = fields.Datetime(
        string='Date de livraison',
        required=True,
        default=_default_delivery_date,
    )
    comment = fields.Text(string='Commentaire')
    remaining_quantity = fields.Float(
        string='Quantité restante',
        compute='_compute_remaining_quantity',
        store=False,
        help="Quantité restante à dispatcher"
    )

    available_quantity = fields.Float(
        string='Quantité disponible',
        compute='_compute_available_quantity',
        store=False
    )

    hold_quantity = fields.Float(string='Quantité réservée', copy=False)

    confirm_dispatch = fields.Boolean(
        string='Dispatch confirmé',
        default=False,
        help="Cochez cette case pour confirmer ce dispatch"
    )

    @api.depends('quantity', 'delivery_ids.quantity', 'delivery_ids.state')
    def _compute_quantities(self):
        for line in self:
            # Quantité livrée : somme des livraisons effectuées
            line.quantity_delivered = sum(
                delivery.quantity 
                for delivery in line.delivery_ids.filtered(lambda d: d.state == 'done')
            )
            
            # Quantité planifiée : somme des livraisons non annulées
            line.quantity_planned = sum(
                delivery.quantity 
                for delivery in line.delivery_ids.filtered(lambda d: d.state != 'cancel')
            )
            
            # Reste à livrer
            line.quantity_remaining = line.quantity - line.quantity_delivered

    @api.constrains('quantity', 'delivery_ids')
    def _check_quantities(self):
        for line in self:
            if line.quantity_delivered > line.quantity:
                raise ValidationError(_("La quantité totale planifiée ne peut pas dépasser la quantité commandée"))
            if line.quantity < 0:
                raise ValidationError(_("La quantité ne peut pas être négative"))

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line(self):
        if self.sale_order_line_id:
            self.quantity = self.sale_order_line_id.product_uom_qty
            self.partner_id = self.sale_order_id.partner_id

    @api.depends('quantity', 'quantity_delivered')
    def _compute_state(self):
        for line in self:
            if line.quantity_delivered == 0:
                line.state = 'draft'
            elif line.quantity_delivered < line.quantity:
                line.state = 'confirmed'
            else:
                line.state = 'done'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.quantity:
                record._create_movement(record.quantity)
        return records

    def _create_movement(self, quantity):
        self.ensure_one()
        if quantity > 0:
            self.env['pre.sale.order.movements'].create({
                'sale_order_id': self.sale_order_id.id,
                'product_id': self.product_id.id,
                'pre_sale_order_line_id': self.id,
                'credit': quantity,
            })

    def unlink(self):
        # Récupérer les commandes liées avant la suppression
        sale_orders = self.mapped('sale_order_id')
        
        # Créer les mouvements de libération des quantités
        for line in self:
            # 1. Trouver et supprimer le mouvement crédit correspondant
            credit_move = self.env['pre.sale.order.movements'].search([
                ('sale_order_id', '=', line.sale_order_id.id),
                ('product_id', '=', line.product_id.id),
                ('credit', '=', line.quantity),
                ('description', 'ilike', f'Dispatch pour {line.partner_id.name}')
            ], limit=1)
            
            if credit_move:
                credit_move.unlink()
            
            # 2. Créer un nouveau mouvement pour tracer la libération
            self.env['pre.sale.order.movements'].create({
                'sale_order_id': line.sale_order_id.id,
                'product_id': line.product_id.id,
                'debit': line.quantity,
                'description': f"Libération - Annulation dispatch pour {line.partner_id.name}"
            })
        
        # Suppression standard SANS supprimer la ligne de commande
        result = super().unlink()
        
        # Recalculer les totaux
        for order in sale_orders:
            order._compute_delivery_status()
            order._compute_movement_totals()
        
        return result

    def write(self, vals):
        if 'quantity' in vals:
            self._create_movement(vals['quantity'])
        return super().write(vals)

    @api.onchange('product_id', 'sale_order_id')
    def _onchange_product_id(self):
        if self.product_id:
            self._compute_available_quantity()

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        self.delivery_address_id = False

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            return {
                'domain': {
                    'product_id': [('id', 'in', self.sale_order_id.order_line.mapped('product_id').ids)]
                }
            }

    @api.depends('sale_order_id.order_line.product_uom_qty', 'sale_order_id.pre_sale_order_line_ids.quantity')
    def _compute_available_quantity(self):
        for record in self:
            # Récupérer la quantité totale de la ligne de commande
            sale_line = record.sale_order_id.order_line.filtered(
                lambda l: l.product_id == record.product_id
            )
            total_quantity = sum(sale_line.mapped('product_uom_qty'))
            
            # Calculer la quantité déjà allouée
            allocated_quantity = sum(
                record.sale_order_id.pre_sale_order_line_ids.filtered(
                    lambda l: l.product_id == record.product_id and l.id != record.id
                ).mapped('quantity')
            )
            
            record.available_quantity = total_quantity - allocated_quantity

    @api.constrains('quantity', 'available_quantity')
    def _check_quantity(self):
        for record in self:
            if record.quantity > record.available_quantity:
                raise ValidationError(_("La quantité ne peut pas dépasser la quantité disponible"))

    @api.depends('sale_order_id.order_line.product_uom_qty', 'sale_order_id.pre_sale_order_line_ids.quantity')
    def _compute_remaining_quantity(self):
        for line in self:
            total_ordered = sum(line.sale_order_id.order_line.mapped('product_uom_qty'))
            already_dispatched = sum(
                line.sale_order_id.pre_sale_order_line_ids.filtered(
                    lambda l: l.id != line.id and l.product_id == line.product_id
                ).mapped('quantity')
            )
            line.remaining_quantity = total_ordered - already_dispatched - line.quantity

    def create_delivery(self):
        self.ensure_one()
        if self.is_preso:
            if not self.order_id.state == 'sale':
                raise ValidationError(_(
                    'Impossible de créer une livraison : la commande doit être confirmée'
                    ' pour la ligne de préparation %s'
                ) % self.name)
            if not self.confirm_dispatch:
                raise ValidationError(_(
                    'Impossible de créer une livraison : le dispatch doit être confirmé'
                    ' pour la ligne de préparation %s'
                ) % self.name)
        return super().create_delivery()

    