from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class PreSaleOrderMovements(models.Model):
    _name = 'pre.sale.order.movements'
    _description = 'Mouvements de préparation de commande'
    _order = 'create_date DESC'

    # Champs relationnels
    sale_order_id = fields.Many2one('sale.order', string='Commande', required=True)
    product_id = fields.Many2one('product.product', string='Produit', required=True)
    pre_sale_order_line_id = fields.Many2one('pre.sale.order.line', string='Ligne de préparation')
    
    # Champs de mouvement
    description = fields.Char(required=True)
    debit = fields.Float(string='Débit', default=0.0)
    credit = fields.Float(string='Crédit', default=0.0)
    running_balance = fields.Float(string='Solde courant', compute='_compute_running_balance', store=True)
    
    # Champs techniques
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    create_date = fields.Datetime(readonly=True, index=True)

    _sql_constraints = [
        ('check_movement_values', 'CHECK(debit >= 0 AND credit >= 0)', 
         'Les valeurs de débit et crédit doivent être positives')
    ]

    @api.depends('credit', 'debit')
    def _compute_running_balance(self):
        for record in self:
            record.running_balance = record.debit - record.credit

    @api.constrains('debit', 'credit')
    def _check_movement(self):
        for movement in self:
            if movement.debit > 0 and movement.credit > 0:
                raise ValidationError(_("Un mouvement ne peut pas avoir à la fois un débit et un crédit"))

    def name_get(self):
        return [(
            movement.id, 
            f"{movement.create_date.strftime('%Y-%m-%d %H:%M')} - "
            f"{movement.product_id.name} - "
            f"{movement.description}"
        ) for movement in self]

    @api.model_create_multi
    def create(self, vals_list):
        # Forcer la date de création pour le tri
        for vals in vals_list:
            vals['create_date'] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        # Empêcher la modification de la date de création
        if 'create_date' in vals:
            del vals['create_date']
        return super().write(vals)
    
    