from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta

class TestDivisionMixin(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Création d'un pays de test
        cls.country_fr = cls.env['res.country'].create({
            'name': 'France',
            'code': 'FR'
        })
        
        # Création d'un autre pays pour les tests
        cls.country_be = cls.env['res.country'].create({
            'name': 'Belgique',
            'code': 'BE'
        })

        # Dates de test
        cls.today = date.today()
        cls.tomorrow = cls.today + timedelta(days=1)
        cls.yesterday = cls.today - timedelta(days=1)

    def test_parent_child_hierarchy(self):
        """Test détaillé de la hiérarchie parent/enfant"""
        # Création région
        region = self.env['res.country.division'].create({
            'name': 'Occitanie',
            'subdivision_code': 'OCC',
            'country_id': self.country_fr.id,
            'date_start': self.today,
            'date_end': self.tomorrow
        })

        # Création département
        dept = self.env['res.country.division'].create({
            'name': 'Haute-Garonne',
            'subdivision_code': 'HGA',
            'country_id': self.country_fr.id,
            'parent_id': region.id,
            'date_start': self.today,
            'date_end': self.tomorrow
        })

        # Création ville
        city = self.env['res.country.division'].create({
            'name': 'Toulouse',
            'subdivision_code': 'TLS',
            'country_id': self.country_fr.id,
            'parent_id': dept.id,
            'date_start': self.today,
            'date_end': self.tomorrow
        })

        # Test des niveaux
        self.assertEqual(region.level, 0)
        self.assertEqual(dept.level, 1)
        self.assertEqual(city.level, 2)

        # Test des noms complets
        self.assertEqual(region.complete_name, 'Occitanie')
        self.assertEqual(dept.complete_name, 'Occitanie - Haute-Garonne')
        self.assertEqual(city.complete_name, 'Occitanie - Haute-Garonne - Toulouse')

        # Test des relations parent/enfant
        self.assertEqual(city.parent_id, dept)
        self.assertEqual(dept.parent_id, region)
        self.assertFalse(region.parent_id)

        self.assertIn(dept, region.child_ids)
        self.assertIn(city, dept.child_ids)
        self.assertFalse(city.child_ids)

    def test_parent_constraints(self):
        """Test des contraintes sur les relations parent/enfant"""
        region_fr = self.env['res.country.division'].create({
            'name': 'Occitanie',
            'subdivision_code': 'OCC',
            'country_id': self.country_fr.id,
            'date_start': self.today,
            'date_end': self.tomorrow
        })

        region_be = self.env['res.country.division'].create({
            'name': 'Wallonie',
            'subdivision_code': 'WAL',
            'country_id': self.country_be.id,
            'date_start': self.today,
            'date_end': self.tomorrow
        })

        # Test: impossible d'avoir un parent d'un autre pays
        with self.assertRaises(ValidationError):
            self.env['res.country.division'].create({
                'name': 'Test',
                'subdivision_code': 'TST',
                'country_id': self.country_fr.id,
                'parent_id': region_be.id,
                'date_start': self.today,
                'date_end': self.tomorrow
            })

        # Test: impossible d'être son propre parent
        with self.assertRaises(ValidationError):
            region_fr.write({'parent_id': region_fr.id})

    def test_recursive_hierarchy(self):
        """Test des fonctions récursives sur la hiérarchie"""
        # Création d'une hiérarchie complète
        region = self.env['res.country.division'].create({
            'name': 'Occitanie',
            'subdivision_code': 'OCC',
            'country_id': self.country_fr.id,
            'date_start': self.today,
            'date_end': self.tomorrow
        })

        dept = self.env['res.country.division'].create({
            'name': 'Haute-Garonne',
            'subdivision_code': 'HGA',
            'country_id': self.country_fr.id,
            'parent_id': region.id,
            'date_start': self.today,
            'date_end': self.tomorrow
        })

        city = self.env['res.country.division'].create({
            'name': 'Toulouse',
            'subdivision_code': 'TLS',
            'country_id': self.country_fr.id,
            'parent_id': dept.id,
            'date_start': self.today,
            'date_end': self.tomorrow
        })

        # Test get_full_hierarchy
        hierarchy = city.get_full_hierarchy()
        self.assertEqual(len(hierarchy), 3)
        self.assertEqual(hierarchy[0], region)
        self.assertEqual(hierarchy[1], dept)
        self.assertEqual(hierarchy[2], city)

        # Test is_ancestor_of
        self.assertTrue(region.is_ancestor_of(city))
        self.assertTrue(region.is_ancestor_of(dept))
        self.assertTrue(dept.is_ancestor_of(city))
        self.assertFalse(city.is_ancestor_of(dept))
        self.assertFalse(city.is_ancestor_of(region))

        # Test get_children_recursive
        all_children = region.get_children_recursive()
        self.assertEqual(len(all_children), 2)  # dept et city
        self.assertIn(dept, all_children)
        self.assertIn(city, all_children)

        # Test avec profondeur limitée
        first_level = region.get_children_recursive(depth=1)
        self.assertEqual(len(first_level), 1)  # seulement dept
        self.assertIn(dept, first_level)
        self.assertNotIn(city, first_level)