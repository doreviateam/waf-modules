import sys

if 'pytest' in sys.modules:
    # Pour les tests
    from unittest.mock import MagicMock
    
    class MockModels:
        class AbstractModel:
            def __init__(self, *args, **kwargs):
                self._name = 'mixin.iso.3166'
                self._description = 'ISO 3166 Mixin'
    
    models = MockModels()
    fields = MagicMock()
    api = MagicMock()
else:
    # Pour Odoo
    from odoo import models, fields, api, _
    from odoo.exceptions import UserError, ValidationError
    from datetime import timedelta
    import re




class ISO3166Mixin(models.AbstractModel):
    """
    Mixin pour les codes ISO 3166-2
    """
    _name = 'mixin.iso.3166'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'ISO 3166 Mixin'
    _parent_name = 'parent_id'
    _parent_store = True
    _parent_order = 'complete_name'
    _order = 'complete_name'


    
    _sql_constraints = [
        ('uniq_subdivision_code_per_country', 'UNIQUE(country_id, subdivision_code)', 'Le code ISO 3166 doit être unique par pays.'),
        ('uniq_complete_code', 'UNIQUE(complete_code)', 'Le code ISO 3166 doit être unique.'),
        ('check_dates', 'CHECK(date_start IS NOT NULL AND date_end IS NOT NULL AND date_start <= date_end)', 'Les dates doivent être renseignées et la date de début doit être antérieure ou égale à la date de fin.')
    ]


    active = fields.Boolean(string='Actif', default=True, help='Indique si la subdivision administrative est active')

    name = fields.Char(string='Nom', required=True, translate=True, help='Nom officiel de la subdivision administrative', tracking=True)
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    complete_name = fields.Char(string='Nom complet', compute='_compute_complete_name', store=True, help='Nom complet incluant les parents')
    
    subdivision_code = fields.Char(string='Code de la subdivision', index=True, required=True, help='Code ISO 3166-2 de la subdivision administrative', tracking=True)
    complete_code = fields.Char(string='Code complet', compute='_compute_complete_code', index=True, store=True, help='Code complet incluant le pays et la subdivision')

    country_id = fields.Many2one(comodel_name='res.country', string='Pays', required=True,  help='Pays auquel la subdivision administrative appartient')
    parent_id = fields.Many2one(comodel_name='mixin.iso.3166', string='Subdivision parente', ondelete='restrict', index=True, help='Subdivision administrative parente')
    parent_path = fields.Char(index=True, unaccent=False, help='Chemin des parents')
    child_ids = fields.One2many(comodel_name='mixin.iso.3166', inverse_name='parent_id', string='Subdivisions enfants', help='Subdivisions enfants')

    level = fields.Integer(string='Niveau', compute='_compute_level', store=True, help='Niveau de la subdivision administrative dans la hiérarchie')

    date_start = fields.Date(string='Date de début', help='Date de début de validité de la subdivision administrative', index=True)
    date_end = fields.Date(string='Date de fin', help='Date de fin de validité de la subdivision administrative', index=True)

    is_valid = fields.Boolean(string='Valide', compute='_compute_is_valid', search='_search_is_valid', help='Indique si la subdivision est valide à la date du jour')

    @api.depends('date_start', 'date_end')
    def _compute_is_valid(self):
        today = fields.Date.today()
        for record in self:
            record.is_valid = record.date_start <= today <= record.date_end

    def _search_is_valid(self, operator, value):
        today = fields.Date.today()
        if operator == '=' and value:
            domain = [
                ('date_start', '<=', today),
                ('date_end', '>=', today)
            ]
        elif operator == '=' and not value:
            domain = [
                '|',
                ('date_start', '>', today),
                ('date_end', '<', today)
            ]
        return domain

    @api.depends('parent_id')
    def _compute_complete_name(self):
        """Calcule le nom complet de la subdivision administrative."""
        for record in self:
            record.complete_name = record.name
            if record.parent_id:
                record.complete_name = f"{record.parent_id.complete_name} - {record.complete_name}"

    @api.depends('parent_id')
    def _compute_level(self):
        """Calcule le niveau de la subdivision administrative dans la hiérarchie."""
        for record in self:
            record.level = record.parent_path.count('/') if record.parent_path else 0

    @api.depends('country_id', 'subdivision_code')
    def _compute_complete_code(self):
        """Calcule le code complet de la subdivision administrative."""
        for record in self:
            if record.country_id and record.subdivision_code:
                record.complete_code = f"{record.country_id.code}-{record.subdivision_code}".upper()
            else:
                record.complete_code = False

    # Validation des codes de subdivision
    @api.constrains('subdivision_code')
    def _check_subdivision_code(self):
        """Vérifie que le code de subdivision est valide."""
        for record in self:
            if record.subdivision_code and not re.match(r'^[A-Z]{3}$', record.subdivision_code):
                raise ValidationError(_('Le code de subdivision doit contenir exactement 3 lettres majuscules.'))
    
    @api.constrains('parent_id')
    def _check_parent_id(self):
        """Vérifie que le parent de la subdivision est valide."""
        for record in self:
            # Vérifie que la subdivision et son parent sont du même pays
            if record.parent_id and record.parent_id.country_id != record.country_id:
                raise ValidationError(_('La subdivision et son parent doivent appartenir au même pays.'))
            # Vérifie que la subdivision n'est pas son propre parent
            if record.parent_id == record:
                raise ValidationError(_('La subdivision ne peut être son propre parent.'))
            # Détecte les boucles dans la hiérarchie
            if record.parent_id:
                current_parent = record.parent_id
                while current_parent:
                    if current_parent == record:
                        raise ValidationError(_('Détection de boucle dans la hiérarchie des subdivisions.'))
                    current_parent = current_parent.parent_id
    

    @api.constrains('complete_code')
    def _check_3166_format(self):
        """Vérifie que le code ISO 3166 est valide."""
        for record in self:
            if not record.complete_code:            
                continue
                
            # Séparation du code pays et du code de subdivision
            parts = record.complete_code.split('-')
            if len(parts) != 2:
                raise ValidationError(_('Le format du code doit être XX-YYY'))
                
            country_code, subdivision = parts
            
            # Vérification du code pays
            if country_code != record.country_id.code:
                raise ValidationError(_('Le code pays doit correspondre au pays sélectionné'))
                
            # Vérification du code de subdivision
            if subdivision != record.subdivision_code:
                raise ValidationError(_('Incohérence entre le code de subdivision et le code complet'))
            
    
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Vérifie que la date de début est antérieure à la date de fin."""
        for record in self:
            if record.date_start and record.date_end and record.date_start > record.date_end:
                raise ValidationError(_('La date de début ne peut être postérieure à la date de fin.'))
            if not (record.date_start or record.date_end) or not (record.date_start and record.date_end):
                raise ValidationError(_('Les dates de début et de fin ne peuvent être nulles.'))
             
    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f'[{record.code}] {record.name}'
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Permet la recherche par code, nom et validité"""
        args = args or []
        domain = []
        
        # Recherche par nom/code
        if name:
            domain = ['|', '|',
                ('complete_code', operator, name),
                ('subdivision_code', operator, name),
                ('name', operator, name)
            ]
    
        # Ajout du filtre de date si présent dans le contexte
        check_date = self.env.context.get('check_date')
        if check_date:
            domain.extend([
                ('date_start', '<=', check_date),
                ('date_end', '>=', check_date)
            ])
        
        return self.search(domain + args, limit=limit).name_get()
    

    def get_full_hierarchy(self):
        """Retourne la hiérarchie complète de la subdivision"""
        self.ensure_one()
        hierarchy = []
        current = self
        while current:
            hierarchy.insert(0, current)
            current = current.parent_id
        return hierarchy

    def is_ancestor_of(self, other):
        """Vérifie si cette subdivision est un ancêtre d'une autre"""
        self.ensure_one()
        return other.parent_path and other.parent_path.startswith(self.parent_path)

    def get_children_recursive(self, depth=None):
        """Retourne toutes les subdivisions enfants récursivement"""
        domain = [('parent_path', 'like', self.parent_path + '%')]
        if depth:
            domain.append(('level', '<=', self.level + depth))
        return self.search(domain)
    
    def is_valid_at_date(self, check_date=None):
        """
        Vérifie si la subdivision est valide à une date donnée
        :param check_date: Date à vérifier (date du jour par défaut)
        :return: Boolean
        """
        self.ensure_one()
        if not check_date:
            check_date = fields.Date.today()
        return self.date_start <= check_date <= self.date_end
    
    @api.constrains('date_start', 'date_end', 'country_id', 'subdivision_code')
    def _check_date_overlap(self):
        """Vérifie qu'il n'y a pas de chevauchement temporel pour un même code"""
        for record in self:
            overlaps = self.search([
                ('id', '!=', record.id),
                ('country_id', '=', record.country_id.id),
                ('subdivision_code', '=', record.subdivision_code),
                '|',
                    '&', ('date_start', '<=', record.date_start), ('date_end', '>=', record.date_start),
                    '&', ('date_start', '<=', record.date_end), ('date_end', '>=', record.date_end)
            ])
            if overlaps:
                raise ValidationError(_('Il existe déjà une subdivision avec ce code pour cette période'))
            
    def get_valid_successor(self):
        """
        Retourne la subdivision qui succède à celle-ci (chronologiquement)
        """
        self.ensure_one()
        return self.search([
            ('country_id', '=', self.country_id.id),
            ('subdivision_code', '=', self.subdivision_code),
            ('date_start', '>', self.date_end)
        ], order='date_start', limit=1)

    def get_valid_predecessor(self):
        """
        Retourne la subdivision qui précède celle-ci (chronologiquement)
        """
        self.ensure_one()
        return self.search([
            ('country_id', '=', self.country_id.id),
            ('subdivision_code', '=', self.subdivision_code),
            ('date_end', '<', self.date_start)
        ], order='date_end desc', limit=1)

    def get_history(self):
        """
        Retourne l'historique complet des versions de cette subdivision
        """
        self.ensure_one()
        return self.search([
            ('country_id', '=', self.country_id.id),
            ('subdivision_code', '=', self.subdivision_code)
        ], order='date_start')
    
    def extend_validity(self, new_end_date):
        """
        Étend la période de validité jusqu'à une nouvelle date
        """
        self.ensure_one()
        if new_end_date <= self.date_end:
            raise ValidationError(_("La nouvelle date de fin doit être postérieure à l'actuelle"))
        
        successor = self.get_valid_successor()
        if successor and new_end_date >= successor.date_start:
            raise ValidationError(_("La nouvelle période chevauche une subdivision existante"))
        
        self.write({'date_end': new_end_date})

    def split_validity(self, split_date):
        """
        Divise la période de validité en deux à une date donnée
        """
        self.ensure_one()
        if not (self.date_start < split_date < self.date_end):
            raise ValidationError(_("La date de division doit être comprise dans la période de validité"))
        
        new_subdivision = self.copy({
            'date_start': split_date,
            'date_end': self.date_end
        })
        self.write({'date_end': split_date - timedelta(days=1)})
        return new_subdivision
    
    @api.model
    def validate_code_format(self, country_code, subdivision_code):
        """
        Valide le format des codes indépendamment d'un enregistrement
        Utile pour la validation avant création
        """
        if not re.match(r'^[A-Z]{2}$', country_code):
            raise ValidationError(_('Le code pays doit contenir exactement 2 lettres majuscules'))
        if not re.match(r'^[A-Z]{3}$', subdivision_code):
            raise ValidationError(_('Le code de subdivision doit contenir exactement 3 lettres majuscules'))
        return True

    def check_hierarchy_consistency(self):
        """
        Vérifie la cohérence de toute la hiérarchie
        """
        self.ensure_one()
        issues = []
        
        # Vérification des dates par rapport aux parents
        current = self
        while current.parent_id:
            parent = current.parent_id
            if current.date_start < parent.date_start or current.date_end > parent.date_end:
                issues.append(_("Incohérence de dates avec le parent %s") % parent.complete_code)
            current = parent
        
        # Vérification des dates par rapport aux enfants
        for child in self.child_ids:
            if child.date_start < self.date_start or child.date_end > self.date_end:
                issues.append(_("Incohérence de dates avec l'enfant %s") % child.complete_code)
        
        if issues:
            raise ValidationError("\n".join(issues))
        return True
    
    def export_hierarchy(self):
        """
        Exporte la hiérarchie complète au format dictionnaire
        """
        self.ensure_one()
        result = {
            'code': self.complete_code,
            'name': self.name,
            'date_start': self.date_start.isoformat(),
            'date_end': self.date_end.isoformat(),
            'children': []
        }
        
        for child in self.child_ids:
            result['children'].append(child.export_hierarchy())
        
        return result

    @api.model
    def import_hierarchy(self, data, parent_id=False):
        """
        Importe une hiérarchie depuis un dictionnaire
        """
        country_code, subdivision_code = data['code'].split('-')
        country = self.env['res.country'].search([('code', '=', country_code)])
        
        values = {
            'name': data['name'],
            'country_id': country.id,
            'subdivision_code': subdivision_code,
            'date_start': data['date_start'],
            'date_end': data['date_end'],
            'parent_id': parent_id
        }
        
        record = self.create(values)
        
        for child_data in data.get('children', []):
            self.import_hierarchy(child_data, record.id)
        
        return record
