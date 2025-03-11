from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class SaleDispatch(models.Model):
    _name = 'sale.dispatch'
    _description = 'Dispatch de commande'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default='Nouveau'
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État', 
       default='draft',
       tracking=True)

    # Doit être géré à la ligne de dispatch
    # scheduled_date = fields.Date(
    #     string='Date de livraison',
    #     required=True,
    #     tracking=True,
    #     default=fields.Date.context_today
    # )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Commande',
        required=True,
        domain="[('delivery_mode', '=', 'dispatch')]"
    )

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        depends=['sale_order_id.currency_id'],
        store=True,
        string='Devise'
    )

    dispatch_percent_global = fields.Float(
        string='Progression dispatch globale',
        related='sale_order_id.dispatch_percent_global',
        store=True,
        help="Pourcentage global des quantités dispatchées",
        digits=(5, 2)
    )

    dispatch_progress = fields.Float(
        string='Progression',
        compute='_compute_dispatch_progress',
        store=True,
        help="Pourcentage global des quantités dispatchées"
    )

    line_ids = fields.One2many(
        'sale.line.dispatch',
        'dispatch_id',
        string='Lignes'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        related='sale_order_id.company_id',
        store=True
    )

    picking_ids = fields.Many2many(
        'stock.picking',
        string='Bons de livraison',
        copy=False,
        readonly=True
    )

    picking_count = fields.Integer(
        string='Nombre de BL',
        compute='_compute_picking_count'
    )

    mandator_id = fields.Many2one(
        'res.partner',
        string='Mandator',
        required=True)

    commitment_date = fields.Datetime(
        string='Date promise',
        tracking=True,
        help="Date de livraison promise au client"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.dispatch') or _('Nouveau')
        return super().create(vals_list)

    def action_confirm(self):
        """Confirme le dispatch."""
        for dispatch in self:
            if dispatch.state != 'draft':
                raise UserError(_("Seuls les dispatches en brouillon peuvent être confirmés."))
            dispatch.write({'state': 'confirmed'})
            _logger.info(f"Dispatch {dispatch.name} confirmé.")

    def action_done(self):
        """Termine le dispatch."""
        for dispatch in self:
            if dispatch.state != 'confirmed':
                raise UserError(_("Seuls les dispatches confirmés peuvent être terminés."))
            dispatch.write({'state': 'done'})
            _logger.info(f"Dispatch {dispatch.name} terminé.")

    def action_cancel(self):
        """Annule le dispatch."""
        for dispatch in self:
            if dispatch.state not in ['draft', 'confirmed']:
                raise UserError(_("Seuls les dispatches en brouillon ou confirmés peuvent être annulés."))
            dispatch.write({'state': 'cancel'})
            _logger.info(f"Dispatch {dispatch.name} annulé.")

    def action_draft(self):
        """Remet le dispatch en brouillon."""
        for dispatch in self:
            if dispatch.state != 'cancel':
                raise UserError(_("Seuls les dispatches annulés peuvent être remis en brouillon."))
            dispatch.write({'state': 'draft'})

    def action_view_pickings(self):
        """Affiche les bons de livraison associés."""
        self.ensure_one()
        return {
            'name': _('Bons de livraison'),
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
        """Vérifie que la commande est bien liée à un mode de livraison 'dispatch'."""
        for dispatch in self:
            if dispatch.sale_order_id.delivery_mode != 'dispatch':
                raise ValidationError(_(
                    "La commande doit être configurée pour le mode de livraison 'dispatch'."
                ))

    @api.constrains('line_ids')
    def _check_lines(self):
        """Vérifie qu'il y a au moins une ligne de dispatch."""
        for dispatch in self:
            if not dispatch.line_ids:
                raise ValidationError(_("Un dispatch doit avoir au moins une ligne."))

    @api.depends('line_ids.product_uom_qty', 'sale_order_id.order_line.product_uom_qty')
    def _compute_dispatch_progress(self):
        for dispatch in self:
            total_qty = sum(dispatch.sale_order_id.order_line.mapped('product_uom_qty'))
            dispatched_qty = sum(dispatch.line_ids.mapped('product_uom_qty'))
            dispatch.dispatch_progress = (dispatched_qty / total_qty * 100) if total_qty else 0.0

    @api.onchange('sale_order_id')
    def _onchange_sale_order(self):
        if self.sale_order_id and self.sale_order_id.commitment_date:
            self.commitment_date = self.sale_order_id.commitment_date

    def write(self, vals):
        res = super().write(vals)
        if 'commitment_date' in vals:
            for record in self:
                record.sale_order_id.write({
                    'commitment_date': vals['commitment_date']
                })
        return res

    @api.constrains('line_ids', 'sale_order_id')
    def _check_total_dispatch_quantity(self):
        for dispatch in self:
            # Grouper les lignes par ligne de commande
            lines_by_order_line = {}
            for line in dispatch.line_ids:
                if line.state != 'cancel':
                    if line.sale_order_line_id not in lines_by_order_line:
                        lines_by_order_line[line.sale_order_line_id] = 0
                    lines_by_order_line[line.sale_order_line_id] += line.product_uom_qty

            # Vérifier chaque ligne de commande
            for order_line, total_qty in lines_by_order_line.items():
                if total_qty > order_line.product_uom_qty:
                    raise ValidationError(_(
                        "Le total des quantités dispatchées (%(dispatched)s) ne peut pas dépasser "
                        "la quantité commandée (%(ordered)s) pour le produit %(product)s.",
                        dispatched=total_qty,
                        ordered=order_line.product_uom_qty,
                        product=order_line.product_id.display_name
                    ))