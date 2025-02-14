from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class DeliveryWeekday(models.Model):
    _name = 'delivery.weekday'
    _description = 'Jour de livraison'
    _order = 'sequence'

    name = fields.Char('Nom', required=True)
    sequence = fields.Integer('Séquence', default=10)
    active = fields.Boolean('Actif', default=True)
    code = fields.Char('Code', required=True, size=1)

    # Relations Many2many inverses
    zone_ids = fields.Many2many(
        'delivery.zone',
        'delivery_weekday_zone_rel',
        'weekday_id',
        'zone_id',
        string='Zones de livraison'
    )

    partner_ids = fields.Many2many(
        'res.partner',
        'delivery_weekday_partner_rel',
        'weekday_id',
        'partner_id',
        string='Clients'
    )

    # Ajout d'un champ pour optimiser les requêtes
    delivery_count = fields.Integer(
        string='Nombre de livraisons',
        compute='_compute_delivery_count',
        store=True
    )

    picking_count = fields.Integer(
        string='Nombre de livraisons',
        compute='_compute_picking_count',
        store=True
    )

    sale_order_ids = fields.Many2many(
        'sale.order',
        'delivery_weekday_sale_order_rel',
        'weekday_id',
        'sale_order_id',
        string='Commandes',
        compute='_compute_sale_orders',
        store=True
    )

    @api.depends('sale_order_ids.picking_ids')
    def _compute_picking_count(self):
        for weekday in self:
            pickings = weekday.sale_order_ids.mapped('picking_ids')
            weekday.picking_count = len(pickings.filtered(
                lambda p: p.scheduled_date and 
                fields.Date.from_string(p.scheduled_date).strftime('%u') == weekday.code
            ))

    @api.depends('partner_ids.sale_order_ids')
    def _compute_sale_orders(self):
        for weekday in self:
            weekday.sale_order_ids = weekday.partner_ids.mapped('sale_order_ids')

    @api.depends('sale_order_ids.picking_ids')
    def _compute_picking_count(self):
        for partner in self:
            partner.picking_count = len(partner.sale_order_ids.mapped('picking_ids'))

    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if not record.code or record.code not in ['1', '2', '3', '4', '5', '6', '7']:
                raise ValidationError(_("Le code doit être un chiffre entre 1 et 7"))

    @api.depends('partner_ids.sale_order_ids.picking_ids')
    def _compute_delivery_count(self):
        for weekday in self:
            pickings = self.env['stock.picking'].search([
                ('partner_id', 'in', weekday.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('scheduled_date', '!=', False)
            ])
            weekday.delivery_count = len(pickings.filtered(
                lambda p: fields.Date.from_string(p.scheduled_date).strftime('%u') == weekday.code
            ))



class DeliveryTimeSlot(models.Model):
    _name = 'delivery.time.slot'
    _description = 'Créneau horaire de livraison'
    _order = 'sequence'

    name = fields.Char('Nom', required=True)
    sequence = fields.Integer('Séquence', default=10)
    start_hour = fields.Float('Heure de début', required=True)
    end_hour = fields.Float('Heure de fin', required=True)
    active = fields.Boolean('Actif', default=True)
    
    # Capacité par créneau
    max_deliveries = fields.Integer('Livraisons maximum', default=0)
    
    # Relations Many2many inverses
    zone_ids = fields.Many2many(
        'delivery.zone',
        'delivery_time_slot_zone_rel',
        'time_slot_id',
        'zone_id',
        string='Zones de livraison'
    )

    partner_ids = fields.Many2many(
        'res.partner',
        'delivery_time_slot_partner_rel',
        'time_slot_id',
        'partner_id',
        string='Clients'
    )

    # Ajout de contraintes pour les heures
    _sql_constraints = [
        ('check_hours', 
         'CHECK(start_hour >= 0 AND start_hour < 24 AND end_hour > 0 AND end_hour <= 24 AND start_hour < end_hour)',
         'Les heures doivent être valides et l\'heure de début doit être avant l\'heure de fin')
    ]
    
    # Ajout d'un champ calculé pour l'occupation
    occupation_rate = fields.Float(
        string="Taux d'occupation",
        compute='_compute_occupation_rate',
        store=True,
        help="Pourcentage d'occupation du créneau"
    )

    delivery_count = fields.Integer(
        string="Nombre de livraisons",
        compute='_compute_occupation_rate',
        store=True
    )

    @api.constrains('start_hour', 'end_hour')
    def _check_hours(self):
        for slot in self:
            if slot.start_hour < 0 or slot.start_hour >= 24:
                raise ValidationError(_("L'heure de début doit être entre 0 et 24"))
            if slot.end_hour < 0 or slot.end_hour >= 24:
                raise ValidationError(_("L'heure de fin doit être entre 0 et 24"))
            if slot.start_hour >= slot.end_hour:
                raise ValidationError(_("L'heure de début doit être avant l'heure de fin")) 

    @api.depends('partner_ids.delivery_ids', 'max_deliveries')
    def _compute_occupation_rate(self):
        for slot in self:
            domain = [
                ('partner_id', 'in', slot.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'not in', ['cancel', 'draft']),
                ('scheduled_date', '!=', False)
            ]
            
            deliveries = self.env['stock.picking'].search(domain)
            
            # Filtrer les livraisons dans ce créneau horaire
            slot_deliveries = deliveries.filtered(lambda d: 
                float(d.scheduled_date.strftime('%H.%M')) >= slot.start_hour and
                float(d.scheduled_date.strftime('%H.%M')) < slot.end_hour
            )
            
            slot.delivery_count = len(slot_deliveries)
            
            if slot.max_deliveries:
                slot.occupation_rate = (slot.delivery_count / slot.max_deliveries) * 100
            else:
                slot.occupation_rate = 0.0

    def action_view_deliveries(self):
        self.ensure_one()
        return {
            'name': _('Livraisons'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', 'in', self.partner_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'not in', ['cancel', 'draft']),
                ('scheduled_date', '!=', False)
            ],
            'context': {
                'create': False,
                'default_picking_type_code': 'outgoing',
                'search_default_scheduled_date': True
            }
        }

    