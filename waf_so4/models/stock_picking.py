from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Nouveau champ mandator
    mandator_id = fields.Many2one(
        'res.partner',
        string='Mandator',
        help="The mandator who initiated the order",
        tracking=True,
        copy=True
    )

    # On surcharge le champ partner_shipping_id qui est utilisé pour la validation
    partner_shipping_id = fields.Many2one(
        'res.partner',
        compute='_compute_partner_shipping_id',
        store=True,
        readonly=True
    )

    # Désactive explicitement la validation standard
    @api.model
    def _check_company_delivery_address(self):
        _logger.info("_check_company_delivery_address called and bypassed")
        return True

    # Surcharge complète de la méthode de validation
    @api.constrains('partner_id')
    def _check_delivery_address(self):
        # Ne rien faire pour désactiver la validation
        pass

    # Surcharge de la méthode de validation
    @api.constrains('partner_id', 'partner_shipping_id')
    def _check_partner_shipping(self):
        return True

    dispatch_id = fields.Many2one(
        'sale.line.dispatch', 
        string='Dispatch', 
        ondelete='set null'
    )

    delivery_address_id = fields.Many2one(
        'partner.address',
        string='Delivery Address',
        tracking=True,
        index=True
    )

    # Champs calculés pour l'adresse (non stockés)
    delivery_site_name = fields.Char(
        string='Site Name',
        compute='_compute_delivery_address_fields'
    )
    delivery_street = fields.Char(
        string='Street',
        compute='_compute_delivery_address_fields'
    )
    delivery_street2 = fields.Char(
        string='Street 2',
        compute='_compute_delivery_address_fields'
    )
    delivery_city = fields.Char(
        string='City',
        compute='_compute_delivery_address_fields'
    )
    delivery_zip = fields.Char(
        string='ZIP',
        compute='_compute_delivery_address_fields'
    )

    @api.depends('delivery_address_id')
    def _compute_partner_shipping_id(self):
        """Calcule l'adresse de livraison basée sur le contact de livraison de partner.address."""
        for picking in self:
            _logger.info("Computing partner_shipping_id for picking %s using delivery_address_id: %s", 
                        picking.name, picking.delivery_address_id.name if picking.delivery_address_id else 'None')
            picking.partner_shipping_id = picking.delivery_address_id.delivery_contact_id if picking.delivery_address_id else picking.partner_id

    @api.depends('delivery_address_id', 'partner_id')
    def _compute_delivery_address_fields(self):
        for picking in self:
            if picking.delivery_address_id:
                picking.delivery_site_name = picking.delivery_address_id.name
                picking.delivery_street = picking.delivery_address_id.street
                picking.delivery_street2 = picking.delivery_address_id.street2
                picking.delivery_city = picking.delivery_address_id.city
                picking.delivery_zip = picking.delivery_address_id.zip
            else:
                picking.delivery_site_name = False
                picking.delivery_street = False
                picking.delivery_street2 = False
                picking.delivery_city = False
                picking.delivery_zip = False

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
                    # Prix unitaire * quantité livrée
                    line_amount = move.sale_line_id.price_unit * move.product_qty
                    # Appliquer les taxes
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