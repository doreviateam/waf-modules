from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError
from odoo.tools.misc import html_escape
import logging

_logger = logging.getLogger(__name__)

class PartnerAddress(models.Model):
    _name = 'partner.address'
    _description = 'Delivery Address'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id'

    _sql_constraints = [
        ('unique_address', 'unique(name, zip, city, country_id)', 
         'This address already exists in the system.')
    ]

    # Champs relationnels
    partner_ids = fields.Many2many(
        'res.partner',
        'partner_address_rel',
        column1='address_id',
        column2='partner_id',
        string='Associated Customers',
        required=True,
        tracking=True,
        domain="[('company_id', 'in', [False, context.get('force_company', context.get('allowed_company_ids', [])[0] if context.get('allowed_company_ids') else False)])]",
        index=True
    )

    main_partner_id = fields.Many2one(
        'res.partner',
        string='Main Partner',
        compute='_compute_main_partner',
        store=True,
        index=True
    )

    company_ids = fields.Many2many(
        'res.company',
        string='Companies',
        compute='_compute_companies',
        store=True
    )

    sale_line_dispatch_ids = fields.One2many(
        'sale.line.dispatch',
        'delivery_address_id',
        string='Dispatches'
    )

    # Champs d'adresse
    name = fields.Char(string='Name', required=True)
    type = fields.Selection([
        ('delivery', 'Delivery Address'),
        ('contact', 'Contact')
    ], string='Type', required=True, default='delivery')
    active = fields.Boolean(string='Active', default=True)
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    comment = fields.Text(string='Comment')

    # Champs calculés
    dispatch_count = fields.Integer(
        string='Dispatch Count',
        compute='_compute_dispatch_count',
        store=True
    )

    # Nouveau champ pour stocker le contact de livraison créé
    delivery_contact_id = fields.Many2one(
        'res.partner',
        string='Delivery Contact',
        readonly=True
    )

    @api.depends('sale_line_dispatch_ids')
    def _compute_dispatch_count(self):
        for address in self:
            address.dispatch_count = len(address.sale_line_dispatch_ids)

    address_full_name = fields.Html(
        string='Full Name',
        compute='_compute_address_full_name',
        store=True
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        index=True
    )

    @api.depends('name', 'city', 'zip')
    def _compute_display_name(self):
        # Calcul du nom d'affichage basé sur le nom, la ville et le code postal
        for address in self:
            parts = []
            if address.name:
                parts.append(str(address.name))
            if address.city:
                parts.append(str(address.city))
            if address.zip:
                parts.append(str(address.zip))
            address.display_name = ' - '.join(filter(None, parts)) or _('Unnamed')

    @api.depends('partner_ids')
    def _compute_main_partner(self):
        # Récupération du premier partenaire comme partenaire principal
        for address in self:
            address.main_partner_id = address.partner_ids[:1]

    @api.depends('partner_ids.company_id')
    def _compute_companies(self):
        # Calcul des sociétés liées aux partenaires
        for address in self:
            companies = address.partner_ids.mapped('company_id')
            address.company_ids = [(6, 0, companies.ids)]

    @api.depends('name', 'street', 'street2', 'zip', 'city', 'country_id')
    def _compute_address_full_name(self):
        # Construction du nom complet formaté en HTML
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
        # Vérification des contraintes sur les partenaires
        for record in self:
            if not record.partner_ids:
                raise ValidationError(_("An address must be linked to at least one partner."))
            
            companies = record.partner_ids.mapped('company_id')
            if len(companies) > 1:
                raise ValidationError(_("Linked partners must belong to the same company."))

    @api.constrains('zip')
    def _check_zip(self):
        # Vérification du format du code postal
        for record in self:
            if record.zip and not record.zip.strip().isalnum():
                raise ValidationError(_("ZIP code must contain only alphanumeric characters"))

    @api.model_create_multi
    def create(self, vals_list):
        # Normalisation des données à la création
        for vals in vals_list:
            if vals.get('zip'):
                vals['zip'] = vals['zip'].strip().upper()
            if vals.get('city'):
                vals['city'] = vals['city'].strip().title()
            if not vals.get('main_partner_id'):
                vals['main_partner_id'] = self._get_odoo_bot().id
        records = super().create(vals_list)
        for record in records:
            # Créer un contact de livraison associé
            delivery_contact = self.env['res.partner'].create({
                'name': record.name,
                'street': record.street,
                'city': record.city,
                'zip': record.zip,
                'type': 'delivery',
                'parent_id': record.main_partner_id.id,
            })
            record.delivery_contact_id = delivery_contact
        return records

    def write(self, vals):
        # Normalisation des données à la modification
        if vals.get('zip'):
            vals['zip'] = vals['zip'].strip().upper()
        if vals.get('city'):
            vals['city'] = vals['city'].strip().title()
        res = super().write(vals)
        # Mettre à jour le contact de livraison si nécessaire
        if any(f in vals for f in ['name', 'street', 'city', 'zip']):
            for record in self:
                if record.delivery_contact_id:
                    record.delivery_contact_id.write({
                        'name': record.name,
                        'street': record.street,
                        'city': record.city,
                        'zip': record.zip,
                    })
        return res

    def unlink(self):
        # Vérification avant suppression
        if self.env['sale.line.dispatch'].search_count([('delivery_address_id', 'in', self.ids)]):
            raise ValidationError(_("You cannot delete an address that has associated dispatches."))
        # Supprimer les contacts de livraison associés
        self.mapped('delivery_contact_id').unlink()
        return super().unlink()

    def action_view_dispatches(self):
        # Affichage des dispatches liés à l'adresse
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
        # Archivage de l'adresse
        if self.env['sale.line.dispatch'].search_count([
            ('delivery_address_id', 'in', self.ids),
            ('state', 'not in', ['done', 'cancel'])
        ]):
            raise ValidationError(_("You cannot archive an address that has ongoing dispatches."))
        self.write({'active': False})

    def action_unarchive(self):
        # Désarchivage de l'adresse
        self.write({'active': True})

    @api.model
    def _get_odoo_bot(self):
        # Récupération du bot Odoo
        return self.env.ref('base.partner_root')

    @api.onchange('partner_ids')
    def _onchange_partner_ids(self):
        # Mise à jour du partenaire principal lors du changement des partenaires
        if self.partner_ids and not self.main_partner_id:
            self.main_partner_id = self.partner_ids[0]
