from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError
from odoo.tools.misc import html_escape

class PartnerAddress(models.Model):
    _name = 'partner.address'
    _description = 'Adresse du partenaire'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id'

    _sql_constraints = [
        ('unique_address', 'unique(name, zip, city, country_id)', 
         'Cette adresse existe déjà dans le système.')
    ]

    # Champs relationnels
    partner_ids = fields.Many2many(
        'res.partner',
        'partner_address_rel',
        column1='address_id',
        column2='partner_id',
        string='Partenaires liés',
        required=True,
        tracking=True,
        domain="[('company_id', 'in', [False, context.get('force_company', context.get('allowed_company_ids', [])[0] if context.get('allowed_company_ids') else False)])]",
        index=True
    )

    main_partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire principal',
        compute='_compute_main_partner',
        store=True,
        index=True
    )

    company_ids = fields.Many2many(
        'res.company',
        string='Sociétés',
        compute='_compute_companies',
        store=True
    )

    sale_line_dispatch_ids = fields.One2many(
        'sale.line.dispatch',
        'delivery_address_id',
        string='Dispatches'
    )

    # Champs d'adresse
    name = fields.Char(
        string='Nom',
        required=True,
        tracking=True,
        help="Nom de l'adresse ou du site",
        index=True
    )
    street = fields.Char(string='Rue', tracking=True)
    street2 = fields.Char(string='Rue 2', tracking=True)
    zip = fields.Char(
        string='Code postal',
        required=True,
        tracking=True,
        index=True
    )
    city = fields.Char(
        string='Ville',
        required=True,
        tracking=True,
        index=True
    )
    state_id = fields.Many2one(
        'res.country.state', 
        string='Département',
        tracking=True,
        index=True
    )
    country_id = fields.Many2one(
        'res.country', 
        string='Pays',
        required=True,
        tracking=True,
        default=lambda self: self.env.company.country_id.id,
        index=True
    )

    # Champs de configuration
    type = fields.Selection([
        ('delivery', 'Adresse de livraison'),
        ('invoice', 'Adresse de facturation'),
        ('other', 'Autre')
    ], string="Type d'adresse",
       default='delivery',
       required=True,
       tracking=True,
       index=True
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
        index=True
    )

    # Champs calculés
    dispatch_count = fields.Integer(
        string='Nombre de dispatches',
        compute='_compute_dispatch_count',
        store=True
    )

    address_full_name = fields.Html(
        string='Nom complet',
        compute='_compute_address_full_name',
        store=True
    )

    display_name = fields.Char(
        string='Nom affiché',
        compute='_compute_display_name',
        store=True,
        index=True
    )

    @api.depends('name', 'city', 'zip')
    def _compute_display_name(self):
        for address in self:
            address.display_name = f"{address.name} ({address.zip} {address.city})" if address.city and address.zip else address.name

    @api.depends('partner_ids')
    def _compute_main_partner(self):
        for address in self:
            address.main_partner_id = address.partner_ids[:1]

    @api.depends('partner_ids.company_id')
    def _compute_companies(self):
        for address in self:
            companies = address.partner_ids.mapped('company_id')
            address.company_ids = [(6, 0, companies.ids)]

    @api.depends('sale_line_dispatch_ids')
    def _compute_dispatch_count(self):
        for address in self:
            address.dispatch_count = len(address.sale_line_dispatch_ids)

    @api.depends('name', 'street', 'street2', 'zip', 'city', 'country_id')
    def _compute_address_full_name(self):
        for address in self:
            parts = []
            if address.name:
                parts.append(f"<strong>{html_escape(address.name)}</strong><br/>")
            if address.street:
                parts.append(f"{html_escape(address.street)}<br/>")
            if address.street2:
                parts.append(f"{html_escape(address.street2)}<br/>")
            if address.zip or address.city:
                parts.append(f"{html_escape(address.zip or '')} {html_escape(address.city or '')}</br>")
            if address.country_id:
                parts.append(f"{html_escape(address.country_id.name)}")
            
            address.address_full_name = " ".join(filter(None, parts))

    @api.constrains('partner_ids')
    def _check_partner_ids(self):
        for record in self:
            if not record.partner_ids:
                raise ValidationError(_("Une adresse doit être liée à au moins un partenaire."))
            
            companies = record.partner_ids.mapped('company_id')
            if len(companies) > 1:
                raise ValidationError(_("Les partenaires liés doivent appartenir à la même société."))

    @api.constrains('zip')
    def _check_zip(self):
        for record in self:
            if record.zip and not record.zip.strip().isalnum():
                raise ValidationError(_("Le code postal ne doit contenir que des caractères alphanumériques"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('zip'):
                vals['zip'] = vals['zip'].strip().upper()
            if vals.get('city'):
                vals['city'] = vals['city'].strip().title()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('zip'):
            vals['zip'] = vals['zip'].strip().upper()
        if vals.get('city'):
            vals['city'] = vals['city'].strip().title()
        return super().write(vals)

    def unlink(self):
        if self.env['sale.line.dispatch'].search_count([('delivery_address_id', 'in', self.ids)]):
            raise ValidationError(_("Vous ne pouvez pas supprimer une adresse qui a des dispatches associés."))
        return super().unlink()

    def action_view_dispatches(self):
        self.ensure_one()
        return {
            'name': _('Dispatches'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.line.dispatch',
            'view_mode': 'tree,form',
            'domain': [('delivery_address_id', '=', self.id)],
            'context': {'default_delivery_address_id': self.id}
        }

    def action_archive(self):
        if self.env['sale.line.dispatch'].search_count([
            ('delivery_address_id', 'in', self.ids),
            ('state', 'not in', ['done', 'cancel'])
        ]):
            raise ValidationError(_("Vous ne pouvez pas archiver une adresse qui a des dispatches en cours."))
        self.write({'active': False})

    def action_unarchive(self):
        self.write({'active': True})
