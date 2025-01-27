from odoo.tests import common
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from odoo import fields
import time



class TestIso19115Mixin(common.TransactionCase):
    def setUp(self):
        super().setUp()
        # Création d'un modèle de test qui utilise le mixin
        self.env['ir.model.data'].create({
            'name': 'test_location_model',
            'model': 'test.localization',
            'module': 'watergile_location_iso',
            'res_id': 1,
        })
        
        # Données de test valides
        self.valid_coords = {
            'latitude': 48.8566,
            'longitude': 2.3522,
            'altitude': 35.0,
            'coordinate_source': 'gps',
            'temporal_extent_begin': fields.Datetime.now(),
        }

    def test_01_create_location(self):
        """Test la création d'une localisation avec données valides"""
        location = self.env['test.localization'].create(self.valid_coords)
        self.assertEqual(location.coordinate_status, 'validated')
        self.assertTrue(location.last_update)
        self.assertEqual(location.coordinate_source, 'gps')

    def test_02_invalid_coordinates(self):
        """Test la validation des coordonnées invalides"""
        invalid_coords = dict(self.valid_coords)
        
        # Test latitude invalide
        invalid_coords['latitude'] = 91.0
        with self.assertRaises(ValidationError):
            self.env['test.localization'].create(invalid_coords)

        # Test longitude invalide
        invalid_coords['latitude'] = 45.0
        invalid_coords['longitude'] = 181.0
        with self.assertRaises(ValidationError):
            self.env['test.localization'].create(invalid_coords)

    def test_03_temporal_validation(self):
        """Test la validation temporelle"""
        # Création avec dates invalides
        invalid_dates = dict(self.valid_coords)
        invalid_dates['temporal_extent_begin'] = fields.Datetime.now()
        invalid_dates['temporal_extent_end'] = fields.Datetime.now() - timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            self.env['test.localization'].create(invalid_dates)

    def test_04_coordinate_status_computation(self):
        """Test le calcul du statut des coordonnées"""
        location = self.env['test.localization'].create(self.valid_coords)
        
        # Test statut initial
        self.assertEqual(location.coordinate_status, 'validated')
        
        # Test expiration
        location.write({
            'temporal_extent_end': fields.Datetime.now() - timedelta(days=1)
        })
        self.assertEqual(location.coordinate_status, 'expired')
        
        # Test brouillon
        location.write({
            'temporal_extent_begin': False
        })
        self.assertEqual(location.coordinate_status, 'draft')

    def test_05_update_coordinates(self):
        """Test la mise à jour des coordonnées"""
        location = self.env['test.localization'].create(self.valid_coords)
        
        new_coords = {
            'latitude': 45.7578,
            'longitude': 4.8320,
            'altitude': 170.0
        }
        
        # Test mise à jour via méthode dédiée
        location.update_coordinates(**new_coords)
        
        self.assertEqual(location.latitude, new_coords['latitude'])
        self.assertEqual(location.longitude, new_coords['longitude'])
        self.assertEqual(location.altitude, new_coords['altitude'])
        self.assertTrue(location.last_update)

    def test_06_manual_source_validation(self):
        """Test la validation spécifique pour source manuelle"""
        manual_coords = dict(self.valid_coords)
        manual_coords['coordinate_source'] = 'manual'
        
        # Test création sans coordonnées
        manual_coords['latitude'] = False
        manual_coords['longitude'] = False
        
        with self.assertRaises(UserError):
            self.env['test.localization'].create(manual_coords)

    def test_07_get_coordinates_display(self):
        """Test l'affichage formaté des coordonnées"""
        location = self.env['test.localization'].create(self.valid_coords)
        display = location.get_coordinates_display()
        
        self.assertEqual(display['latitude'], round(self.valid_coords['latitude'], 6))
        self.assertEqual(display['longitude'], round(self.valid_coords['longitude'], 6))
        self.assertEqual(display['altitude'], round(self.valid_coords['altitude'], 2))
        self.assertEqual(display['source'], 'GPS')

    def test_08_write_tracking(self):
        """Test le suivi des modifications"""
        location = self.env['test.localization'].create(self.valid_coords)
        initial_update = location.last_update
        initial_user = location.last_update_user_id
        
        # Attente pour assurer une différence de timestamp
        time.sleep(1)
        
        location.write({'latitude': 43.2964})
        
        self.assertNotEqual(location.last_update, initial_update)
        self.assertEqual(location.last_update_user_id, self.env.user)