from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    mandator_id = fields.Many2one(
        'res.partner',
        string='Mandator',
        help="The mandator who initiated the order",
        tracking=True,
        copy=True
    )

    stakeholder_id = fields.Many2one(
        'res.partner',
        string='Stakeholder',
        tracking=True,
        copy=True,
        domain="[('is_company', '=', True)]",
        help="The stakeholder concerned by this delivery",
        compute='_compute_stakeholder_id',
        store=True
    )

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Delivery Address',
        tracking=True,
        domain="[('type', '=', 'delivery')]",
        help="Delivery address for this picking"
    )

    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Delivery Location',
        tracking=True,
        index=True
    )

    # Champs d'adresse de livraison
    delivery_site_name = fields.Char(
        string='Site Name',
        compute='_compute_delivery_address_fields',
        store=True
    )
    delivery_street = fields.Char(
        string='Street',
        compute='_compute_delivery_address_fields',
        store=True
    )
    delivery_street2 = fields.Char(
        string='Street 2',
        compute='_compute_delivery_address_fields',
        store=True
    )
    delivery_city = fields.Char(
        string='City',
        compute='_compute_delivery_address_fields',
        store=True
    )
    delivery_zip = fields.Char(
        string='ZIP',
        compute='_compute_delivery_address_fields',
        store=True
    )

    dispatch_id = fields.Many2one(
        'sale.dispatch', 
        string='Dispatch', 
        ondelete='set null'
    )

    @api.depends('delivery_address_id', 'delivery_address_id.name', 
                 'delivery_address_id.street', 'delivery_address_id.street2',
                 'delivery_address_id.city', 'delivery_address_id.zip',
                 'partner_shipping_id', 'partner_shipping_id.name',
                 'partner_shipping_id.street', 'partner_shipping_id.street2',
                 'partner_shipping_id.city', 'partner_shipping_id.zip')
    def _compute_delivery_address_fields(self):
        for picking in self:
            if picking.delivery_address_id:
                picking.delivery_site_name = picking.delivery_address_id.name
                picking.delivery_street = picking.delivery_address_id.street
                picking.delivery_street2 = picking.delivery_address_id.street2
                picking.delivery_city = picking.delivery_address_id.city
                picking.delivery_zip = picking.delivery_address_id.zip
            elif picking.partner_shipping_id:
                picking.delivery_site_name = picking.partner_shipping_id.name
                picking.delivery_street = picking.partner_shipping_id.street
                picking.delivery_street2 = picking.partner_shipping_id.street2
                picking.delivery_city = picking.partner_shipping_id.city
                picking.delivery_zip = picking.partner_shipping_id.zip
            else:
                picking.delivery_site_name = False
                picking.delivery_street = False
                picking.delivery_street2 = False
                picking.delivery_city = False
                picking.delivery_zip = False

    @api.onchange('delivery_address_id')
    def _onchange_delivery_address_id(self):
        """Met à jour l'adresse de livraison uniquement pour les BL créés via dispatch"""
        for picking in self:
            if picking.dispatch_id and picking.delivery_address_id.delivery_contact_id:
                picking.partner_shipping_id = picking.delivery_address_id.delivery_contact_id

    def _get_report_base_filename(self):
        self.ensure_one()
        if self.dispatch_id:
            return 'Delivery Note - Dispatch - %s' % self.name
        return super()._get_report_base_filename()

    @api.depends('move_ids', 'move_ids.sale_line_id', 'move_ids.product_qty')
    def _compute_amounts(self):
        for picking in self:
            amount_untaxed = 0.0
            amount_tax = 0.0

            for move in picking.move_ids:
                if move.sale_line_id and move.product_qty > 0:
                    line_amount = move.sale_line_id.price_unit * move.product_qty
                    taxes = move.sale_line_id.tax_id.compute_all(
                        line_amount,
                        currency=move.sale_line_id.currency_id,
                        quantity=1.0,
                        product=move.product_id,
                        partner=move.picking_id.partner_id
                    )
                    amount_untaxed += taxes['total_excluded']
                    amount_tax += sum(t.get('amount', 0.0) for t in taxes['taxes'])

            picking.amount_untaxed = amount_untaxed
            picking.amount_tax = amount_tax
            picking.amount_total = amount_untaxed + amount_tax

    amount_untaxed = fields.Monetary(
        string='Subtotal',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    amount_tax = fields.Monetary(
        string='Taxes',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True
    )

    @api.depends('dispatch_id', 'dispatch_id.stakeholder_id')
    def _compute_stakeholder_id(self):
        for picking in self:
            if picking.dispatch_id:
                picking.stakeholder_id = picking.dispatch_id.stakeholder_id
            else:
                picking.stakeholder_id = False

    @api.onchange('dispatch_id')
    def _onchange_dispatch_id(self):
        """Met à jour le stakeholder quand le dispatch change"""
        for picking in self:
            if picking.dispatch_id:
                picking.stakeholder_id = picking.dispatch_id.stakeholder_id
            else:
                picking.stakeholder_id = False 