from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class MassDispatchWizard(models.TransientModel):
    _name = 'mass.dispatch.wizard'
    _description = 'Assistant de création de dispatches en masse'

    sale_order_id = fields.Many2one('sale.order', string='Commande', required=True)
    line_ids = fields.One2many('mass.dispatch.wizard.line', 'wizard_id', string='Lignes')
    warning_message = fields.Text('Message d\'avertissement')
    delivery_addresses = fields.Many2many(
        'partner.address',
        string='Adresses de livraison',
        compute='_compute_delivery_addresses'
    )

    @api.depends('sale_order_id')
    def _compute_delivery_addresses(self):
        for wizard in self:
            wizard.delivery_addresses = self.env['partner.address'].search([
                ('partner_ids', 'in', wizard.sale_order_id.partner_id.id)
            ])

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        
        for wizard in records:
            if wizard.sale_order_id:
                wizard_lines = []
                
                # Récupérer la première adresse de livraison disponible
                default_address = wizard.delivery_addresses[:1]
                
                # Filtrer les lignes de commande avec quantité disponible > 0
                for line in wizard.sale_order_id.order_line:
                    # Calculer la quantité disponible
                    dispatched_qty = sum(
                        d.product_uom_qty 
                        for d in line.dispatch_ids 
                        if d.state != 'cancel'
                    )
                    available_qty = line.product_uom_qty - dispatched_qty
                    
                    # Ne créer une ligne que si la quantité disponible est > 0
                    if available_qty > 0 and line.product_id:  # Vérifier que product_id existe
                        wizard_lines.append({
                            'wizard_id': wizard.id,
                            'sale_order_line_id': line.id,
                            'product_id': line.product_id.id,
                            'delivery_address_id': default_address.id,  # Ajouter l'adresse par défaut
                            'quantity_to_dispatch': available_qty,
                            'scheduled_date': wizard.sale_order_id.commitment_date or fields.Date.today(),
                        })
                
                if wizard_lines:
                    self.env['mass.dispatch.wizard.line'].create(wizard_lines)
        
        return records

    def action_validate(self):
        self.ensure_one()
        dispatches = self.env['sale.line.dispatch']
        
        # 1. Création des dispatches en état 'draft'
        for line in self.line_ids:
            if line.quantity_to_dispatch > 0 and line.delivery_address_id:
                vals = {
                    'sale_order_id': self.sale_order_id.id,
                    'sale_order_line_id': line.sale_order_line_id.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity_to_dispatch,
                    'delivery_address_id': line.delivery_address_id.id,
                    'product_uom': line.sale_order_line_id.product_uom.id,
                    'scheduled_date': line.scheduled_date,
                    'state': 'draft',
                }
                new_dispatch = self.env['sale.line.dispatch'].create(vals)
                dispatches |= new_dispatch
        
        # 2. Vérifier si la commande est entièrement dispatchée
        self.sale_order_id._compute_dispatch_status()
        
        return {'type': 'ir.actions.act_window_close'}

    @api.onchange('sale_order_id')
    def _onchange_sale_order(self):
        if self.sale_order_id:
            # Calculer les lignes disponibles
            available_lines = []
            for line in self.sale_order_id.order_line:
                dispatched_qty = sum(
                    d.product_uom_qty 
                    for d in line.dispatch_ids 
                    if d.state != 'cancel'
                )
                if line.product_uom_qty - dispatched_qty > 0:
                    available_lines.append(line.id)
            
            return {
                'context': {'available_lines': available_lines}
            }

class MassDispatchWizardLine(models.TransientModel):
    _name = 'mass.dispatch.wizard.line'
    _description = 'Ligne d\'assistant de création de dispatches'

    wizard_id = fields.Many2one('mass.dispatch.wizard', string='Wizard', required=True, ondelete='cascade')
    sale_order_line_id = fields.Many2one('sale.order.line', string='Ligne de commande', required=True)
    product_id = fields.Many2one(
        'product.product', 
        string='Article', 
        required=True,
        default=lambda self: self._get_default_product()
    )
    
    # Ajout du champ delivery_address_id
    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Adresse de livraison',
        required=True
    )
    
    # Quantité disponible (calculée)
    available_qty = fields.Float(
        'Quantité disponible',
        compute='_compute_available_qty',
        store=False,
        help="Quantité restante à dispatcher sur la ligne de commande"
    )
    
    # Quantité à dispatcher
    quantity_to_dispatch = fields.Float(
        string='Quantité à dispatcher',
        required=True
    )

    # Date prévue
    scheduled_date = fields.Date(
        string='Date prévue',
        required=True,
        default=fields.Date.today
    )

    @api.depends('sale_order_line_id', 'sale_order_line_id.dispatch_ids.product_uom_qty',
                'sale_order_line_id.dispatch_ids.state')
    def _compute_available_qty(self):
        for line in self:
            if line.sale_order_line_id:
                # Quantité totale de la ligne de commande
                total_qty = line.sale_order_line_id.product_uom_qty
                
                # Quantité déjà dispatchée dans les dispatches existants
                dispatched_qty = sum(
                    d.product_uom_qty 
                    for d in line.sale_order_line_id.dispatch_ids 
                    if d.state != 'cancel'
                )
                
                # La quantité disponible est simplement la différence
                line.available_qty = total_qty - dispatched_qty
            else:
                line.available_qty = 0.0

    @api.onchange('wizard_id.sale_order_id')
    def _onchange_wizard_sale_order(self):
        """Filtre les lignes de commande disponibles."""
        domain = [('order_id', '=', False)]
        
        if self.wizard_id.sale_order_id:
            # Uniquement les lignes de la commande sélectionnée
            domain = [
                ('order_id', '=', self.wizard_id.sale_order_id.id)  # Restreint à la commande courante
            ]
            
            # Si des lignes sont déjà dans le wizard, les exclure
            if self.wizard_id.line_ids:
                used_lines = self.wizard_id.line_ids.mapped('sale_order_line_id').ids
                domain.append(('id', 'not in', used_lines))
        
        return {'domain': {'sale_order_line_id': domain}}

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id(self):
        if self.sale_order_line_id:
            self.product_id = self.sale_order_line_id.product_id
            # Calculer d'abord la quantité disponible
            self._compute_available_qty()
            # Ensuite seulement, définir la quantité à dispatcher
            self.quantity_to_dispatch = self.available_qty or 0.0

    @api.constrains('quantity_to_dispatch', 'available_qty')
    def _check_quantity(self):
        for line in self:
            if line.quantity_to_dispatch > line.available_qty:
                raise ValidationError(_(
                    "La quantité à dispatcher (%s) ne peut pas dépasser "
                    "la quantité disponible (%s) pour l'article %s"
                ) % (
                    line.quantity_to_dispatch,
                    line.available_qty,
                    line.product_id.name
                ))
            if line.quantity_to_dispatch < 0:
                raise ValidationError(_("La quantité à dispatcher ne peut pas être négative."))

    @api.onchange('quantity_to_dispatch')
    def _onchange_quantity(self):
        if not self.quantity_to_dispatch:
            return
            
        if self.quantity_to_dispatch < 0:
            self.quantity_to_dispatch = 0
            return {
                'warning': {
                    'title': _('Quantité invalide'),
                    'message': _('La quantité ne peut pas être négative.')
                }
            }
        
        total_qty = self.sale_order_line_id.product_uom_qty
        dispatched_qty = sum(
            d.product_uom_qty 
            for d in self.sale_order_line_id.dispatch_ids 
            if d.state != 'cancel'
        )
        max_qty = total_qty - dispatched_qty
        
        if self.quantity_to_dispatch > max_qty:
            self.quantity_to_dispatch = max_qty
            return {
                'warning': {
                    'title': _('Quantité excessive'),
                    'message': _('La quantité dépasse la quantité disponible.')
                }
            }

    def _get_default_scheduled_date(self):
        if self.wizard_id and self.wizard_id.sale_order_id:
            return self.wizard_id.sale_order_id.commitment_date or fields.Date.today()
        return fields.Date.today()

    @api.model
    def default_get(self, fields_list):
        # Ajouter des valeurs par défaut
        defaults = super().default_get(fields_list)
        if 'sale_order_line_id' in defaults:
            sale_line = self.env['sale.order.line'].browse(defaults['sale_order_line_id'])
            defaults['product_id'] = sale_line.product_id.id
        return defaults 

    @api.depends('sale_order_line_id', 'sale_order_line_id.product_id')
    def _compute_product_id(self):
        for line in self:
            if line.sale_order_line_id and line.sale_order_line_id.product_id:
                line.product_id = line.sale_order_line_id.product_id 

    def _get_default_product(self):
        """Retourne le produit par défaut basé sur la ligne de commande."""
        if self.sale_order_line_id:
            return self.sale_order_line_id.product_id
        return False

    @api.model
    def create(self, vals):
        """Surcharge de create pour s'assurer que product_id est défini."""
        if vals.get('sale_order_line_id') and not vals.get('product_id'):
            sale_line = self.env['sale.order.line'].browse(vals['sale_order_line_id'])
            vals['product_id'] = sale_line.product_id.id
        return super().create(vals) 