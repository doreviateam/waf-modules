from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TestCountryZone(TransactionCase):
    """Test des zones géographiques"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _logger.info("Début de setUpClass pour TestCountryZone")

        # Création de pays
        cls.france = cls.env['res.country'].create({
            'name': 'France',
            'code': 'FR',
        })
        _logger.info(f"Pays trouvé : {cls.france.name}")

        cls.guadeloupe = cls.env['res.country'].create({
            'name': 'Guadeloupe',
            'code': 'GP',
        })
        _logger.info(f"Pays trouvé : {cls.guadeloupe.name}")

        cls.belgique = cls.env['res.country'].create({
            'name': 'Belgique',
            'code': 'BE',
        })
        _logger.info(f"Pays trouvé : {cls.belgique.name}")

        cls.martinique = cls.env['res.country'].create({
            'name': 'Martinique',
            'code': 'MQ',
        })
        _logger.info(f"Pays trouvé : {cls.martinique.name}")

    # Création de zones
    def test_zone_creation(self):
        """Test de la création de zones"""

        # Création d'une zone
        zone_europe = self.env['res.country.zone'].create({
            'name': 'Union Européenne',
            'code': 'EU',
            'description': 'Zone géographique de l\'Union Européenne',
        })
        self.assertEqual(zone_europe.name, 'Union Européenne')
        self.assertEqual(zone_europe.code, 'EU')
        self.assertTrue(zone_europe.active)

        zone_antilles = self.env['res.country.zone'].create({
            'name': 'Antilles',
            'code': 'ANT',
            'description': 'Zone géographique des Antilles',
        })
        self.assertEqual(zone_antilles.name, 'Antilles')
        self.assertEqual(zone_antilles.code, 'ANT')
        self.assertTrue(zone_antilles.active)

    # Ajout de pays à une zone
    def test_zone_countries_add(self):
        """Test de l'ajout/suppression de pays à une zone"""

        # Création zone européenne
        zone_europe = self.env['res.country.zone'].create({
            'name': 'Union Européenne',
            'code': 'EU',
            'description': 'Zone géographique de l\'Union Européenne',
        })
        # Ajout des pays dans zone européenne
        zone_europe.write({'country_ids': [(4, self.france.id), (4, self.belgique.id)]})
        self.assertIn(self.france, zone_europe.country_ids)
        self.assertIn(self.belgique, zone_europe.country_ids)

        # Création zone antilles
        zone_antilles = self.env['res.country.zone'].create({
            'name': 'Antilles',
            'code': 'ANT',
            'description': 'Zone géographique des Antilles',
        })
        # Ajout des pays dans zone antilles
        zone_antilles.write({'country_ids': [(4, self.guadeloupe.id), (4, self.martinique.id)]})
        self.assertIn(self.guadeloupe, zone_antilles.country_ids)
        self.assertIn(self.martinique, zone_antilles.country_ids)

        # Suppression des pays dans zone européenne
        zone_europe.write({'country_ids': [(3, self.france.id), (3, self.belgique.id)]})
        self.assertNotIn(self.france, zone_europe.country_ids)
        self.assertNotIn(self.belgique, zone_europe.country_ids)

        # Suppression des pays dans zone antilles
        zone_antilles.write({'country_ids': [(3, self.guadeloupe.id), (3, self.martinique.id)]})
        self.assertNotIn(self.guadeloupe, zone_antilles.country_ids)
        self.assertNotIn(self.martinique, zone_antilles.country_ids)

    # Test de la suppression d'une zone
    def test_zone_delete_with_countries(self):
        """Je ne peux pas supprimer une zone si elle contient des pays"""

        # Création zone avec pays
        zone_1 = self.env['res.country.zone'].create({
            'name': 'Zone 1',
            'code': 'Z1',
            'description': 'Zone géographique 1',
        })

        # Ajout de pays dans la zone
        zone_1.write({'country_ids': [(4, self.france.id), (4, self.belgique.id)]})
         # Tentative de suppression de la zone avec pays impossible
        with self.assertRaises(ValidationError, msg="On ne peut pas supprimer la zone car elle contient des pays"):
            zone_1.unlink()

        # Création zone sans pays
        zone_2 = self.env['res.country.zone'].create({
            'name': 'Zone 2',
            'code': 'Z2',
            'description': 'Zone géographique 2',
        })
        # Suppression de la zone sans pays
        zone_2.unlink() # Suppression de la zone sans problème

    # Test de contraintes de validation avec absence de nom
    def test_zone_validation_name(self):
        """Je ne peux pas créer une zone sans nom"""
        with self.assertRaises(ValidationError, msg="On ne peut pas créer une zone sans nom"):
            self.env['res.country.zone'].create({
                'code': 'Z3',
                'description': 'Zone géographique 3',
            })

    # Test de contraintes de validation avec absence de code
    def test_zone_validation_code(self):
        """Je ne peux pas créer une zone sans code"""
        with self.assertRaises(ValidationError, msg="On ne peut pas créer une zone sans code"):
            self.env['res.country.zone'].create({
                'name': 'Zone 4',
                'description': 'Zone géographique 4',
            })

    # Test de contraintes de code unique par zone
    def test_zone_validation_code_unique(self):
        """Je ne peux pas créer deux zones avec le même code"""
        # Création première zone
        self.env['res.country.zone'].create({
            'name': 'Zone 5',
            'code': 'Z5',
            'description': 'Zone géographique 5',
        })
        
        # Tentative de création d'une zone avec le même code
        with self.assertRaises(ValidationError, msg="On ne peut pas créer deux zones avec le même code"):
            self.env['res.country.zone'].create({
                'name': 'Zone 6',
                'code': 'Z5',
                'description': 'Zone géographique 6',
            })

    # Test de contraintes de validation avec code en minuscules
    def test_zone_validation_code_lowercase(self):
        """Je ne peux pas créer une zone avec un code en minuscules"""
        with self.assertRaises(ValidationError, msg="On ne peut pas créer une zone avec un code en minuscules"):
            self.env['res.country.zone'].create({
                'name': 'Zone 7',
                'code': 'z7',
                'description': 'Zone géographique 7',
            })
    
    # Test de contraintes de validation code de moins de 2 ou plus de 3 caractères
    def test_zone_validation_code_length(self):
        """Je ne peux pas créer une zone avec un code de moins de 2 ou plus de 3 caractères"""
        # Test code trop court
        with self.assertRaises(ValidationError, msg="On ne peut pas créer une zone avec un code trop court"):
            self.env['res.country.zone'].create({
                'name': 'Zone 8',
                'code': 'Z',
                'description': 'Zone géographique 8',
            })

        # Test code trop long
        with self.assertRaises(ValidationError, msg="On ne peut pas créer une zone avec un code trop long"):
            self.env['res.country.zone'].create({
                'name': 'Zone 9',
                'code': 'ZZZZ',
                'description': 'Zone géographique 9',
            })

    # Test de recherche de zone par code
    def test_zone_search(self):
        """Test des fonctionnalités de recherche"""
        # Création des zones de test
        zone_a = self.env['res.country.zone'].create({
            'name': 'Zone A',
            'code': 'ZA',
            'description': 'Zone géographique A',
            'country_ids': [(4, self.france.id)]
        })
        
        zone_b = self.env['res.country.zone'].create({
            'name': 'Zone B',
            'code': 'ZB',
            'description': 'Zone géographique B',
            'country_ids': [(4, self.france.id)]
        })

        # Test recherche par code exact
        zone_found = self.env['res.country.zone'].search([('code', '=', 'ZA')])
        self.assertEqual(len(zone_found), 1)
        self.assertEqual(zone_found, zone_a)

        # Test recherche insensible à la casse
        zone_found = self.env['res.country.zone'].search([('code', 'ilike', 'za')])
        self.assertEqual(len(zone_found), 1)
        self.assertEqual(zone_found, zone_a)

        # Test recherche par pays
        zones_france = self.env['res.country.zone'].search([('country_ids', 'in', self.france.id)])
        self.assertEqual(len(zones_france), 2)
        self.assertIn(zone_a, zones_france)
        self.assertIn(zone_b, zones_france)



