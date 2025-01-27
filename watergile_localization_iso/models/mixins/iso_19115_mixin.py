import sys

if 'pytest' in sys.modules:
    # Pour les tests
    from unittest.mock import MagicMock
    
    class MockModels:
        class AbstractModel:
            def __init__(self, *args, **kwargs):
                self._name = 'mixin.iso.19115'
                self._description = 'ISO 19115 Mixin'
    
    models = MockModels()
    fields = MagicMock()
    api = MagicMock()
else:
    # Pour Odoo
    from odoo import models, fields, api, _
    from odoo.exceptions import UserError, ValidationError



class Iso19115Mixin(models.AbstractModel):
    """
    Mixin pour les localisations conformes aux normes ISO 19115.
    Permet d'implément la norme ISO 19115 pour la gestion des métadonnées géographiques.

    ce mixin fournit les champs et méthodes nécessaires pour gérer :
    - les coordonnées de localisation géographiques
    - la traçabilité temporelle des données de localisation
    - la validation et le statut des coordonnées
    - les sources des coordonnées
    - la précision des coordonnées
    - la résolution spatiale
    """
    
    _name = 'mixin.iso.19115'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'ISO 19115 Mixin'

    
    active = fields.Boolean(default=True, string='Actif', help='Permet d\'archiver la localisation')

    latitude = fields.Float(string='Latitude', digits=(10, 8), help='Latitude de la localisation en degrés décimaux (WGS 84)', group_operator=False, index=True)
    longitude = fields.Float(string='Longitude', digits=(10, 8), help='Longitude de la localisation en degrés décimaux (WGS 84)', group_operator=False, index=True)
    altitude = fields.Float(string='Altitude', digits=(10, 2), help='Altitude de la localisation en mètres par rapport au niveau de la mer', group_operator=False)
    
    temporal_extent_begin = fields.Datetime(string='Date de début de validité', help='Date de début de validité de la donnnée de localisation')
    temporal_extent_end = fields.Datetime(string='Date de fin de validité', help='Date de fin de validité de la donnnée de localisation')
    
    spatial_resolution = fields.Float(string='Résolution spatiale (m)', digits=(10, 2), help='Résolution spatiale de la localisation en mètres')
    
    coordinate_source = fields.Selection(string='Source des coordonnées', selection='_get_coordinate_source_selection', required=True, default='other', help='Source des coordonnées de la localisation', tracking=True)
    coordinate_status = fields.Selection(string='Statut des coordonnées', selection=[
                                                                                ('validated', 'Validée'),
                                                                                ('expired', 'Expirée'), 
                                                                                ('draft', 'Brouillon')], 
                                                                                compute='_compute_coordinate_status',
                                                                                store=True,
                                                                                index=True,
                                                                                help='Statut des coordonnées de la localisation')
    
    coordinate_precision = fields.Float(string='Précision (m)', digits=(10,2), help='Précision de la mesure en mètres')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('temporal_extent_begin'):
                vals['temporal_extent_begin'] = fields.Datetime.now()
        return super().create(vals_list)
    
    def write(self, vals):
        """
        Mise à jour de la localisation avec les valeurs par défaut
        """
        if not vals.get('temporal_extent_begin'):
            vals['temporal_extent_begin'] = fields.Datetime.now()
        
        if not vals.get('coordinate_source'):
            vals['coordinate_source'] = 'other'
        if not vals.get('coordinate_status'):
            vals['coordinate_status'] = 'draft'
        return super().write(vals)
    
    def validate_coordinates_batch(self):
        """Validation par lot des coordonnées de localisation"""
        for record in self:
            if record.coordinate_status == 'draft':
                record.update_coordinates(record.latitude, record.longitude, record.altitude)

    def _get_coordinate_source_selection(self):
        """
        Centralisation des sources des coordonnées pour la localisation
        """
        sources = [
                    ('gps', _('GPS')),  
                    ('map', _('Carte')),    
                    ('address', _('Géocodage adresse')),
                    ('manual', _('Saisie manuelle')), 
                    ('other', _('Autre'))
                ]
        return sources
    
    @api.depends('temporal_extent_begin', 'temporal_extent_end', 'coordinate_source')
    def _compute_coordinate_status(self):
        """
        Calcul du statut des coordonnées de la localisation
        """
        now = fields.Datetime.now()
        for record in self:
            if not record.temporal_extent_begin:
                record.coordinate_status = 'draft'
            elif record.temporal_extent_end and record.temporal_extent_end < now:
                record.coordinate_status = 'expired'
            elif record.temporal_extent_begin > now or record.temporal_extent_end > now:
                if record.coordinate_source == 'manual':
                    raise UserError(_('La donnée de localisation n\'est pas valide'))
                else:
                    record.coordinate_status = 'expired'
            else:
                record.coordinate_status = 'validated'
    
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """
        Vérification des coordonnées de localisation
        """
        for record in self.filtered(lambda r: r.latitude or r.longitude):
            if not (record.latitude and record.longitude):
                raise ValidationError(_('Les coordonnées doivent être complètes'))    
    

    def get_coordinates_display(self):
        """
        Affichage des coordonnées de la localisation
        """
        self.ensure_one()
        return {
            'latitude': round(self.latitude, 6) if self.latitude else False,
            'longitude': round(self.longitude, 6) if self.longitude else False,
            'altitude': round(self.altitude, 2) if self.altitude else False,
            'precision': self.coordinate_precision,
            'source': dict(self._get_coordinate_source_selection()).get(self.coordinate_source)
        }
        
    def update_coordinates(self, latitude, longitude, altitude=None):
        """
        Mise à jour des coordonnées de localisation avec traçabilité
        """
        self.ensure_one()
        source = self.coordinate_source
        vals = {
            'latitude': latitude,
            'longitude': longitude,
            'coordinate_source': source or self.coordinate_source,
            'temporal_extent_begin': fields.Datetime.now(),
        }
        if altitude is not None:
            vals['altitude'] = altitude

        if source == 'manual':
            vals['coordinate_status'] = 'validated'

        return self.write(vals)
        
            
