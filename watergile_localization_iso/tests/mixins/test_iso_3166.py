from datetime import date, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestISO3166Mixin(TransactionCase):

    def setUp(self):
        super().setUp()
        # Création d'un modèle de test qui utilise le mixin
        self.env['ir.model.data'].create({
            'name': 'test_subdivision_model',
            'model': 'test.subdivision',
            'module': 'watergile_localization_iso',
        })

        # Données de test
        self.country_fr = self.env.ref('base.fr')
        self.today = date.today()
        
        # Création d'une subdivision de test
        self.test_subdivision = self.env['test.subdivision'].create({
            'name': 'Île-de-France',
            'country_id': self.country_fr.id,
            'subdivision_code': 'IDF',
            'date_start': self.today,
            'date_end': self.today + timedelta(days=365)
        })

    def test_complete_code_computation(self):
        """Test du calcul du code complet"""
        self.assertEqual(self.test_subdivision.complete_code, 'FR-IDF')

    def test_invalid_subdivision_code(self):
        """Test de la validation du code de subdivision"""
        with self.assertRaises(ValidationError):
            self.env['test.subdivision'].create({
                'name': 'Test Invalid',
                'country_id': self.country_fr.id,
                'subdivision_code': '123',  # Doit être 3 lettres
                'date_start': self.today,
                'date_end': self.today + timedelta(days=365)
            })

    def test_date_constraints(self):
        """Test des contraintes sur les dates"""
        # Test date de fin avant date de début
        with self.assertRaises(ValidationError):
            self.env['test.subdivision'].create({
                'name': 'Test Dates',
                'country_id': self.country_fr.id,
                'subdivision_code': 'TST',
                'date_start': self.today + timedelta(days=10),
                'date_end': self.today
            })

    def test_hierarchy(self):
        """Test de la hiérarchie des subdivisions"""
        # Création d'une subdivision parente
        parent = self.env['test.subdivision'].create({
            'name': 'Parent',
            'country_id': self.country_fr.id,
            'subdivision_code': 'PAR',
            'date_start': self.today,
            'date_end': self.today + timedelta(days=365)
        })

        # Création d'une subdivision enfant
        child = self.env['test.subdivision'].create({
            'name': 'Child',
            'country_id': self.country_fr.id,
            'subdivision_code': 'CHD',
            'parent_id': parent.id,
            'date_start': self.today,
            'date_end': self.today + timedelta(days=365)
        })

        # Test du niveau
        self.assertEqual(parent.level, 0)
        self.assertEqual(child.level, 1)

        # Test du nom complet
        self.assertEqual(child.complete_name, 'Parent - Child')

    def test_unique_constraints(self):
        """Test des contraintes d'unicité"""
        # Test de création d'une subdivision avec le même code
        with self.assertRaises(ValidationError):
            self.env['test.subdivision'].create({
                'name': 'Duplicate',
                'country_id': self.country_fr.id,
                'subdivision_code': 'IDF',  # Déjà utilisé
                'date_start': self.today,
                'date_end': self.today + timedelta(days=365)
            })

    def test_validity_methods(self):
        """Test des méthodes de validité"""
        subdivision = self.test_subdivision
        
        # Test is_valid_at_date
        self.assertTrue(subdivision.is_valid_at_date(self.today))
        self.assertFalse(subdivision.is_valid_at_date(self.today + timedelta(days=366)))

        # Test get_valid_successor
        successor = self.env['test.subdivision'].create({
            'name': 'Successor',
            'country_id': self.country_fr.id,
            'subdivision_code': 'IDF',
            'date_start': self.today + timedelta(days=366),
            'date_end': self.today + timedelta(days=731)
        })
        self.assertEqual(subdivision.get_valid_successor(), successor)

    def test_search_methods(self):
        """Test des méthodes de recherche"""
        # Test de name_search
        results = self.env['test.subdivision'].name_search('IDF')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], self.test_subdivision.id)

        # Test avec date de validité
        results = self.env['test.subdivision'].with_context(
            check_date=self.today + timedelta(days=400)
        ).name_search('IDF')
        self.assertEqual(len(results), 0)