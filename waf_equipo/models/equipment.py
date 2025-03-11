from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class Equipment(models.Model):
    _name = 'equipment'
    _description = 'Équipement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id'


    name = fields.Char(
        'Nom', 
        required=True, 
        tracking=True, 
        index=True
    )

    active = fields.Boolean(default=True)

    product_id = fields.Many2one(
        'product.template', 
        string='Produit', 
        required=True, 
        tracking=True
    )

    image_128 = fields.Image(
        string='Image',
        related='product_id.image_128',
        max_width=128,
        max_height=128
    )

    image_1920 = fields.Image(
        string='Image',
        related='product_id.image_1920',
        max_width=1920,
        max_height=1080
    )

    serial_number = fields.Char(
        'Numéro de série', 
        required=True, 
        tracking=True, 
        index=True
    )

    product_number = fields.Char(
        'Numéro de produit', 
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company', 
        string='Mainteneur', 
        required=True, 
        default=lambda self: self.env.company
    )

    owner_id = fields.Many2one(
        'res.partner', 
        string='Propriétaire', 
        required=True, 
        tracking=True
    )

    partner_id = fields.Many2one(
        'res.partner', 
        string='Détenteur', 
        required=True, 
        tracking=True,
        help='Le détenteur est le partenaire qui utilise l\'équipement'
    )

    address_id = fields.Many2one(
        'partner.address', 
        string='Localisation',
        required=True, 
        tracking=True,
        help='La localisation est le lieu où se trouve l\'équipement'
    )
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('disponible', 'Disponible'),
        ('service', 'En service'),
        ('maintenance', 'En maintenance'),
        ('repair', 'En réparation'),
        ('inactive', 'Hors service'),
    ], string='État', default='draft', tracking=True, index=True)

    manufactured_date = fields.Date(
        'Date de fabrication', 
        default=fields.Date.today, 
        tracking=True
    )

    is_refurbished = fields.Boolean(
        'Reconditionné', 
        default=False, 
        tracking=True
    )

    manufacturer_id = fields.Many2one(
        'res.partner', 
        string='Fabricant', 
        required=True, 
        tracking=True
    )

    service_date_start = fields.Date(
        'Date de mise en service', 
        default=fields.Date.today, 
        tracking=True
    )

    warranty_end_date = fields.Date(
        'Fin de garantie', 
        tracking=True
    )
    
    spare_part_ids = fields.Many2many(
        'product.template',
        'product_equipment_rel',
        'equipment_id',
        'product_id',
        string='Pièces détachées',
        domain="[('id', '!=', product_id), ('detailed_type', 'in', ['consu', 'product'])]",
        tracking=True
    )
    
    notes = fields.Html(
        'Notes', 
        tracking=True)

    age_years = fields.Integer(
        'Âge (années)', 
        compute='_compute_age', 
        store=True
    )

    age_months = fields.Integer(
        'Âge (mois)', 
        compute='_compute_age', 
        store=True
    )

    age_days = fields.Integer(
        'Âge (jours)', 
        compute='_compute_age', 
        store=True
    )

    warranty_status = fields.Selection([
        ('no_warranty', 'Pas de garantie'),
        ('active', 'Garantie active'),
        ('expired', 'Garantie expirée')
    ], string='Statut de la garantie', compute='_compute_warranty_status', store=True)

    maintenance_duration_days = fields.Integer(
        'Durée maintenance (jours)', 
        compute='_compute_maintenance_duration', 
        store=True
    )

    maintenance_duration_hours = fields.Integer(
        'Durée maintenance (heures)', 
        compute='_compute_maintenance_duration', 
        store=True
    )



    _sql_constraints = [
        ('serial_number_uniq', 'unique(serial_number, company_id)', 'Le numéro de série doit être unique par société !')
    ]

    @api.constrains('warranty_end_date', 'service_date_start')
    def _check_dates(self):
        for record in self:
            if record.warranty_end_date and record.service_date_start and record.warranty_end_date < record.service_date_start:
                raise ValidationError(_("La date de fin de garantie ne peut pas être antérieure à la date de mise en service."))

    @api.constrains('owner_id', 'partner_id')
    def _check_owner_detenteur(self):
        for record in self:
            if record.owner_id == record.partner_id:
                raise ValidationError(_("Le propriétaire ne peut pas être le même que le détenteur."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                product = self.env['product.template'].browse(vals.get('product_id'))
                vals['name'] = f"{product.name}"
        return super().create(vals_list)
    
    def action_set_disponible(self):
        self.write({'state': 'disponible'})

    def action_set_active(self):
        self.write({'state': 'service'})

    def action_start_maintenance(self):
        self.write({'state': 'maintenance'})

    @api.depends('service_date_start', 'warranty_end_date')
    def _compute_warranty_status(self):
        today = fields.Date.today()
        for equipment in self:
            if not equipment.warranty_end_date:
                equipment.warranty_status = 'no_warranty'
            elif equipment.warranty_end_date < today:
                equipment.warranty_status = 'expired'
            else:
                equipment.warranty_status = 'active'

    @api.depends('service_date_start')
    def _compute_age(self):
        today = fields.Date.today()
        for equipment in self:
            if equipment.service_date_start:
                age = today - equipment.service_date_start
                equipment.age_years = age.days // 365
                equipment.age_months = (age.days % 365) // 30
                equipment.age_days = age.days % 30
            else:
                equipment.age_years = 0
                equipment.age_months = 0
                equipment.age_days = 0

    @api.depends('state', 'write_date')
    def _compute_maintenance_duration(self):
        for equipment in self:
            if equipment.state in ['maintenance', 'repair']:
                last_write = fields.Datetime.from_string(equipment.write_date)
                duration = datetime.now() - last_write
                equipment.maintenance_duration_days = duration.days
                equipment.maintenance_duration_hours = duration.seconds // 3600
            else:
                equipment.maintenance_duration_days = 0
                equipment.maintenance_duration_hours = 0

    def action_start_repair(self):
        self.write({'state': 'repair'})

    def action_set_inactive(self):
        self.write({'state': 'inactive'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_add_spare_part(self):
        self.ensure_one()
        return {
            'name': _('Ajouter une pièce détachée'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_detailed_type': 'product',
                'default_equipment_ids': [(4, self.id)],
            }
        }

    def action_view_spare_parts(self):
        self.ensure_one()
        return {
            'name': _('Pièces détachées'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.spare_part_ids.ids)],
            'context': {'default_detailed_type': 'product'},
        } 