from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round
from datetime import datetime, timedelta

class CreateDeliveryWizard(models.TransientModel):
    _name = 'create.delivery.wizard'
    _description = 'Assistant de création de livraisons'
    _rec_name = 'order_id'

    # Champs de base optimisés avec index
    order_id = fields.Many2one(
        'sale.order', 
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True
    )
    
    groupment_ids = fields.Many2many(
        'partner.groupment',
        'create_delivery_wizard_groupment_rel',
        'wizard_id',
        'groupment_id',
        related='order_id.groupment_ids',
        readonly=True,
    )

    # Champs de livraison multi-zones
    delivery_zone_ids = fields.Many2many(
        'delivery.zone',
        'create_delivery_wizard_zone_rel',
        'wizard_id',
        'zone_id',
        string='Zones de livraison',
        related='order_id.delivery_zone_ids',
        readonly=True
    )

    partner_ids = fields.Many2many(
        'res.partner',
        'create_delivery_wizard_partner_rel',
        'wizard_id',
        'partner_id',
        string='Points de livraison',
        required=True,
        domain="[('id', 'in', available_partner_ids)]",
        check_company=True,
    )

    available_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_available_partner_ids',
        compute_sudo=True,
        store=True,
    )

    delivery_line_ids = fields.One2many(
        'create.delivery.wizard.line',
        'wizard_id',
        string='Lignes de livraison',
        copy=True,
    )

    picking_ids = fields.Many2many(
        'stock.picking',
        string='Bons de livraison',
        readonly=True,
        copy=False,
    )

    # Configuration de livraison
    picking_policy = fields.Selection([
        ('direct', 'Livraison directe'),
        ('one', 'Livrer tout ensemble')
    ], string='Politique de livraison', required=True, default='direct')
    
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Méthode de livraison',
        domain="[('id', 'in', available_carrier_ids)]"
    )

    available_carrier_ids = fields.Many2many(
        'delivery.carrier',
        compute='_compute_available_carriers',
        help="Transporteurs disponibles pour les zones sélectionnées"
    )

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Type d\'opération',
        domain="[('code', '=', 'outgoing')]",
        required=True,
    )

    scheduled_date = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        index=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company
    )

    delivery_note = fields.Text(
        string='Notes de livraison',
    )

    total_weight = fields.Float(
        string='Poids total (kg)',
        compute='_compute_total_weight',
        store=True,
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('done', 'Terminé'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', required=True)

    # Nouveaux champs de contrôle
    delivery_date = fields.Date(
        string='Date de livraison',
        required=True,
        default=fields.Date.context_today
    )

    delivery_time_slot_id = fields.Many2one(
        'delivery.time.slot',
        string='Créneau horaire',
        required=True
    )

    available_time_slot_ids = fields.Many2many(
        'delivery.time.slot',
        compute='_compute_available_time_slots',
        help="Créneaux disponibles selon la zone et la date"
    )

    delivery_capacity_warning = fields.Boolean(
        string='Alerte capacité',
        compute='_compute_delivery_capacity_warning',
        help="Indique si la capacité de livraison est proche du maximum"
    )

    # Champs de validation
    validation_status = fields.Selection([
        ('draft', 'À valider'),
        ('warning', 'Avertissements'),
        ('error', 'Erreurs'),
        ('valid', 'Validé')
    ], default='draft', compute='_compute_validation_status')

    validation_message = fields.Text(
        string='Messages de validation',
        compute='_compute_validation_status'
    )

    # Méthodes de calcul optimisées
    @api.depends('delivery_date', 'partner_ids', 'delivery_zone_ids')
    def _compute_available_time_slots(self):
        for wizard in self:
            available_slots = self.env['delivery.time.slot']
            if not (wizard.delivery_date and wizard.partner_ids and wizard.delivery_zone_ids):
                wizard.available_time_slot_ids = available_slots
                continue

            # Récupération des créneaux communs aux zones
            common_slots = wizard.delivery_zone_ids.mapped('delivery_time_slots')
            
            # Vérification de la disponibilité
            for slot in common_slots:
                domain = [
                    ('scheduled_date', '>=', wizard.delivery_date),
                    ('scheduled_date', '<', wizard.delivery_date + timedelta(days=1)),
                    ('delivery_time_slot_id', '=', slot.id),
                    ('state', 'not in', ['cancel', 'draft'])
                ]
                delivery_count = self.env['stock.picking'].search_count(domain)
                
                if delivery_count < slot.max_deliveries or not slot.max_deliveries:
                    available_slots |= slot

            wizard.available_time_slot_ids = available_slots

    @api.depends('delivery_zone_ids', 'delivery_date')
    def _compute_delivery_capacity_warning(self):
        for wizard in self:
            wizard.delivery_capacity_warning = False
            if not (wizard.delivery_zone_ids and wizard.delivery_date):
                continue

            for zone in wizard.delivery_zone_ids:
                if zone.max_daily_deliveries:
                    domain = [
                        ('delivery_zone_ids', 'in', zone.ids),
                        ('scheduled_date', '>=', wizard.delivery_date),
                        ('scheduled_date', '<', wizard.delivery_date + timedelta(days=1)),
                        ('state', 'not in', ['cancel', 'draft'])
                    ]
                    delivery_count = self.env['stock.picking'].search_count(domain)
                    
                    if delivery_count >= zone.max_daily_deliveries * 0.8:  # 80% de la capacité
                        wizard.delivery_capacity_warning = True
                        break

    @api.depends('partner_ids', 'delivery_line_ids', 'delivery_date', 'delivery_time_slot_id')
    def _compute_validation_status(self):
        for wizard in self:
            status = 'valid'
            messages = []

            # Vérification des partenaires
            if not wizard.partner_ids:
                status = 'error'
                messages.append(_("Aucun partenaire sélectionné"))

            # Vérification des lignes
            if not wizard.delivery_line_ids:
                status = 'error'
                messages.append(_("Aucune ligne de livraison"))
            else:
                for line in wizard.delivery_line_ids:
                    if line.quantity <= 0:
                        status = 'error'
                        messages.append(_("Quantité invalide pour %s") % line.product_id.name)

            # Vérification de la date
            if wizard.delivery_date:
                if wizard.delivery_date < fields.Date.today():
                    status = 'error'
                    messages.append(_("La date de livraison ne peut pas être dans le passé"))
                elif wizard.delivery_capacity_warning:
                    status = 'warning'
                    messages.append(_("La capacité de livraison est proche du maximum"))

            wizard.validation_status = status
            wizard.validation_message = '\n'.join(messages)

    # Méthodes de calcul
    @api.depends('delivery_line_ids.weight')
    def _compute_total_weight(self):
        for wizard in self:
            wizard.total_weight = sum(line.weight for line in wizard.delivery_line_ids)

    @api.depends('order_id.groupment_ids', 'delivery_zone_ids')
    def _compute_available_partner_ids(self):
        for wizard in self:
            groupment_partners = wizard.order_id.groupment_ids.mapped('partner_ids')
            zone_partners = wizard.delivery_zone_ids.mapped('partner_ids')
            wizard.available_partner_ids = groupment_partners & zone_partners

    @api.depends('delivery_zone_ids')
    def _compute_available_carriers(self):
        for wizard in self:
            wizard.available_carrier_ids = wizard.delivery_zone_ids.mapped('delivery_carrier_ids')

    # Méthodes de validation
    @api.constrains('scheduled_date')
    def _check_scheduled_date(self):
        for wizard in self:
            if wizard.scheduled_date < fields.Datetime.now():
                raise ValidationError(_("La date de livraison ne peut pas être dans le passé."))

    @api.constrains('delivery_line_ids')
    def _check_quantities(self):
        for wizard in self:
            for line in wizard.delivery_line_ids:
                if float_compare(line.quantity, 0, precision_digits=2) <= 0:
                    raise ValidationError(
                        _("La quantité doit être supérieure à 0 pour %s") % line.product_id.name
                    )

    @api.constrains('partner_ids', 'delivery_zone_ids')
    def _check_partner_zones(self):
        for wizard in self:
            for partner in wizard.partner_ids:
                if not any(partner in zone.partner_ids for zone in wizard.delivery_zone_ids):
                    raise ValidationError(_(
                        "Le partenaire %s doit appartenir à au moins une des zones "
                        "de livraison sélectionnées"
                    ) % partner.name)

    # Méthodes principales
    def action_create_deliveries(self):
        self.ensure_one()
        orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        for order in orders:
            order.write({
                'delivery_date': self.delivery_date,
                'delivery_time_slot_id': self.delivery_time_slot_id.id,
                'delivery_zone_ids': [(6, 0, self.delivery_zone_ids.ids)],
            })
            if order.picking_ids:
                order.picking_ids.write({
                    'delivery_date': self.delivery_date,
                    'delivery_time_slot_id': self.delivery_time_slot_id.id,
                    'delivery_zone_ids': [(6, 0, self.delivery_zone_ids.ids)],
                })
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'sale.order' and self.env.context.get('active_ids'):
            order = self.env['sale.order'].browse(self.env.context['active_ids'][0])
            if order.delivery_zone_ids:
                res['delivery_zone_ids'] = [(6, 0, order.delivery_zone_ids.ids)]
            if order.delivery_time_slot_id:
                res['delivery_time_slot_id'] = order.delivery_time_slot_id.id
        return res


class CreateDeliveryWizardLine(models.TransientModel):
    _name = 'create.delivery.wizard.line'
    _description = 'Ligne d\'assistant de création de livraison'
    _rec_name = 'product_id'

    wizard_id = fields.Many2one(
        'create.delivery.wizard',
        string='Assistant',
        required=True,
        ondelete='cascade',
        index=True,
    )

    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True,
        ondelete='restrict',
    )

    order_line_id = fields.Many2one(
        'sale.order.line',
        string='Ligne de commande',
        required=True,
        ondelete='cascade',
        index=True,
    )

    quantity = fields.Float(
        string='Quantité à livrer',
        required=True,
        digits='Product Unit of Measure',
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unité de mesure',
        required=True,
        ondelete='restrict',
    )

    weight = fields.Float(
        string='Poids (kg)',
        compute='_compute_weight',
        store=True,
        digits='Stock Weight',
    )

    remaining_qty = fields.Float(
        string='Quantité restante',
        compute='_compute_remaining_qty',
        store=True,
        digits='Product Unit of Measure',
    )

    @api.depends('product_id', 'quantity')
    def _compute_weight(self):
        for line in self:
            line.weight = line.product_id.weight * line.quantity

    @api.depends('order_line_id.product_uom_qty', 'order_line_id.qty_delivered')
    def _compute_remaining_qty(self):
        for line in self:
            delivered = line.order_line_id.qty_delivered
            ordered = line.order_line_id.product_uom_qty
            line.remaining_qty = float_round(
                ordered - delivered,
                precision_digits=2
            )

    @api.constrains('quantity', 'remaining_qty')
    def _check_quantity(self):
        for line in self:
            if float_compare(line.quantity, 0.0, precision_digits=2) <= 0:
                raise ValidationError(_("La quantité doit être positive pour %s") % line.product_id.name)
            if float_compare(line.quantity, line.remaining_qty, precision_digits=2) > 0:
                raise ValidationError(_(
                    "La quantité à livrer (%s) ne peut pas dépasser "
                    "la quantité restante (%s) pour %s"
                ) % (line.quantity, line.remaining_qty, line.product_id.name))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id