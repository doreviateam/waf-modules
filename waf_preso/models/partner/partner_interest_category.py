from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class PartnerInterestCategory(models.Model):
    _name = 'partner.interest.category'
    _description = 'Catégories des centres d\'intérêt'
    _order = 'sequence, name'
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'

    name = fields.Char(
        string='Nom',
        required=True,
        translate=True,
        index=True
    )

    complete_name = fields.Char(
        string='Nom complet',
        compute='_compute_complete_name',
        store=True,
        recursive=True
    )

    parent_id = fields.Many2one(
        'partner.interest.category',
        string='Catégorie parente',
        index=True,
        ondelete='cascade'
    )

    parent_path = fields.Char(
        index=True
    )

    child_ids = fields.One2many(
        'partner.interest.category',
        'parent_id',
        string='Sous-catégories'
    )

    sequence = fields.Integer(
        string='Séquence',
        default=10,
        index=True
    )

    active = fields.Boolean(
        default=True,
        help="Si décoché, cette catégorie sera masquée mais pas supprimée"
    )

    interest_ids = fields.One2many(
        'partner.interest',
        'category_id',
        string='Centres d\'intérêt'
    )

    interest_count = fields.Integer(
        string='Nombre de centres d\'intérêt',
        compute='_compute_interest_count',
        store=True
    )

    total_revenue = fields.Monetary(
        string='Chiffre d\'affaires total',
        compute='_compute_category_stats',
        store=True,
        currency_field='company_currency_id'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company
    )

    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string="Devise",
        readonly=True
    )

    color = fields.Integer(
        string='Couleur',
        help="Couleur utilisée dans les vues kanban"
    )

    description = fields.Text(
        string='Description',
        translate=True
    )

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = f'{category.parent_id.complete_name} / {category.name}'
            else:
                category.complete_name = category.name

    @api.depends('interest_ids', 'child_ids.interest_ids')
    def _compute_interest_count(self):
        for category in self:
            category.interest_count = len(category.interest_ids) + \
                sum(child.interest_count for child in category.child_ids)

    @api.depends('interest_ids.revenue_contribution', 
                'child_ids.total_revenue')
    def _compute_category_stats(self):
        for category in self:
            direct_revenue = sum(interest.revenue_contribution or 0 
                               for interest in category.interest_ids)
            child_revenue = sum(child.total_revenue or 0 
                              for child in category.child_ids)
            category.total_revenue = direct_revenue + child_revenue

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_("Erreur ! Vous ne pouvez pas créer de catégories récursives."))

    def name_get(self):
        if self._context.get('show_complete_name'):
            return [(category.id, category.complete_name) for category in self]
        return super().name_get()

    def action_view_interests(self):
        self.ensure_one()
        return {
            'name': _('Centres d\'intérêt'),
            'type': 'ir.actions.act_window',
            'res_model': 'partner.interest',
            'view_mode': 'tree,form',
            'domain': [('category_id', 'child_of', self.id)],
            'context': {
                'default_category_id': self.id,
                'search_default_category_id': self.id
            }
        }

    @api.model
    def create(self, vals):
        # Vérification du niveau maximum de profondeur
        if vals.get('parent_id'):
            parent = self.browse(vals['parent_id'])
            if len(parent.parent_path.split('/')) >= 3:
                raise ValidationError(_("La profondeur maximale des catégories est de 3 niveaux."))
        return super().create(vals)

    def write(self, vals):
        # Vérification avant déplacement de catégorie
        if vals.get('parent_id'):
            for category in self:
                if category.child_ids and len(self.browse(vals['parent_id']).parent_path.split('/')) >= 2:
                    raise ValidationError(_("Impossible de déplacer une catégorie avec des enfants à ce niveau."))
        return super().write(vals) 
    