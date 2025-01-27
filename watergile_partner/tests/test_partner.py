from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Récupérer la France pour les tests
        cls.france = cls.env['res.country'].search([('code', '=', 'FR')], limit=1)
        cls.belgium = cls.env['res.country'].search([('code', '=', 'BE')], limit=1)
        
        # Créer une société principale
        cls.company_main = cls.env['res.partner'].create({
            'name': 'Maison Mère Test',
            'is_company': True,
            'country_id': cls.france.id,
            'zip': '75001',
        })
        
        # Vérifier que le blaz a été créé automatiquement
        assert cls.company_main.partner_blaz_id, "Le blaz n'a pas été créé automatiquement"
        assert cls.company_main.partner_blaz_id.name == 'Maison Mère Test'
        assert cls.company_main.partner_blaz_id.owner_partner_id == cls.company_main
        
        # Créer une société filiale
        cls.company_child = cls.env['res.partner'].create({
            'name': 'Filiale Test',
            'is_company': True,
            'country_id': cls.france.id,
            'zip': '69001',
        })
        
        # Créer un contact
        cls.contact = cls.env['res.partner'].create({
            'name': 'Contact Test',
            'is_company': False,
            'parent_id': cls.company_main.id,
            'country_id': cls.france.id,
        })

    def test_01_company_blaz_creation(self):
        """Test la création automatique des blaz pour les sociétés"""
        company = self.env['res.partner'].create({
            'name': 'Nouvelle Société',
            'is_company': True,
        })
        
        self.assertTrue(company.partner_blaz_id, "Une société doit avoir un blaz")
        self.assertEqual(company.partner_blaz_id.name, 'Nouvelle Société')
        self.assertEqual(company.partner_blaz_id.owner_partner_id, company)

    def test_02_company_blaz_constraint(self):
        """Test que la contrainte sur les blaz des sociétés fonctionne"""
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Test Company 2',
                'is_company': True,
                'partner_blaz_id': self.company_main.partner_blaz_id.id,
            })

    def test_03_contact_blaz_optional(self):
        """Test que le blaz est optionnel pour les contacts"""
        contact = self.env['res.partner'].create({
            'name': 'Contact Sans Blaz',
            'is_company': False,
            'parent_id': self.company_main.id,
        })
        
        self.assertFalse(contact.partner_blaz_id, "Le blaz doit être optionnel pour les contacts")

    def test_04_contact_blaz_unique(self):
        """Test l'unicité des blaz pour les contacts"""
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Test Contact 2',
                'is_company': False,
                'parent_id': self.company_main.id,
                'partner_blaz_id': self.contact.partner_blaz_id.id,
            })

    def test_05_company_independence(self):
        """Test l'indépendance des sociétés pour la gestion des blaz"""
        # Une filiale peut avoir son propre blaz
        self.assertTrue(self.company_child.partner_blaz_id)
        self.assertNotEqual(self.company_child.partner_blaz_id, self.company_main.partner_blaz_id)
        self.assertEqual(self.company_child.partner_blaz_id.owner_partner_id, self.company_child)

    def test_06_department_region(self):
        """
        Test que le département et la région sont correctement assignés
        en fonction du code postal.
        """
        self.company_main.zip = '75001'
        self.company_main._onchange_zip_country()
        self.assertEqual(self.company_main.department_id, self.company_main.zip_id.department_id)
        self.assertEqual(self.company_main.region_id, self.company_main.department_id.region_id)

    def test_07_badge_display(self):
        """Test l'affichage des badges"""
        # Mettre à jour la hiérarchie
        self.company_child.write({
            'parent_id': self.company_main.id,
            'hierarchy_relation': 'other'
        })
        self.assertEqual(
            self.company_child.company_badge_display,
            'Filiale',
            "Une société avec un parent devrait afficher 'Filiale'"
        )

    def test_08_default_country_france(self):
        """Test que la France est le pays par défaut"""
        partner = self.env['res.partner'].create({
            'name': 'Test Default Country'
        })
        self.assertEqual(partner.country_id, self.france)

    def test_09_zip_required_for_french_company(self):
        """Test que le code postal est obligatoire pour une société française"""
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Société sans code postal',
                'is_company': True,
                'country_id': self.france.id,
            })

    def test_10_zip_not_required_for_foreign_company(self):
        """Test que le code postal n'est pas obligatoire pour une société étrangère"""
        partner = self.env['res.partner'].create({
            'name': 'Société belge',
            'is_company': True,
            'country_id': self.belgium.id,
        })
        self.assertTrue(partner.id)

    def test_11_zip_not_required_for_french_contact(self):
        """Test que le code postal n'est pas obligatoire pour un contact français"""
        partner = self.env['res.partner'].create({
            'name': 'Contact français',
            'is_company': False,
            'country_id': self.france.id,
        })
        self.assertTrue(partner.id)

    def test_12_department_region_computation(self):
        """Test que le département et la région sont correctement calculés"""
        self.assertTrue(self.company_main.state_id, "La région devrait être définie")
        self.assertTrue(self.company_main.department_id, "Le département devrait être défini")
        self.assertEqual(self.company_main.state_id.code, '11', "Devrait être en Île-de-France")

    def test_13_corse_department_computation(self):
        """Test le calcul du département pour la Corse"""
        # Test Corse-du-Sud (2A)
        partner_ajaccio = self.env['res.partner'].create({
            'name': 'Société Corse Sud',
            'is_company': True,
            'country_id': self.france.id,
            'zip': '20000'  # Ajaccio
        })
        
        # Test Haute-Corse (2B)
        partner_bastia = self.env['res.partner'].create({
            'name': 'Société Haute Corse',
            'is_company': True,
            'country_id': self.france.id,
            'zip': '20200'  # Bastia
        })
        
        # Vérifications
        self.assertEqual(partner_ajaccio.department_id.code, '2A')
        self.assertEqual(partner_ajaccio.state_id.code, '94')  # Code région Corse
        
        self.assertEqual(partner_bastia.department_id.code, '2B')
        self.assertEqual(partner_bastia.state_id.code, '94')  # Code région Corse

    def test_14_overseas_department_computation(self):
        """Test le calcul du département et pays pour les DOM"""
        test_data = [
            ('97120', '971', 'GP', '01'),  # Guadeloupe
            ('97220', '972', 'MQ', '02'),  # Martinique
            ('97300', '973', 'GF', '03'),  # Guyane
            ('97400', '974', 'RE', '04'),  # La Réunion
            ('97600', '976', 'YT', '06'),  # Mayotte
        ]
        
        for zip_code, dept_code, country_code, region_code in test_data:
            partner = self.env['res.partner'].create({
                'name': f'Société DOM {country_code}',
                'is_company': True,
                'country_id': self.france.id,
                'zip': zip_code
            })
            
            self.assertEqual(partner.department_id.code, dept_code)
            self.assertEqual(partner.country_id.code, country_code)
            self.assertEqual(partner.state_id.code, region_code)

    def test_15_overseas_collectivities_computation(self):
        """Test le calcul pour les collectivités d'outre-mer (COM)"""
        test_data = [
            ('97133', '977', 'BL'),  # Saint-Barthélemy
            ('97150', '978', 'MF'),  # Saint-Martin
            ('98600', '986', 'WF'),  # Wallis-et-Futuna
            ('98700', '987', 'PF'),  # Polynésie française
            ('98800', '988', 'NC'),  # Nouvelle-Calédonie
        ]
        
        for zip_code, dept_code, country_code in test_data:
            partner = self.env['res.partner'].create({
                'name': f'Société COM {country_code}',
                'is_company': True,
                'country_id': self.france.id,
                'zip': zip_code
            })
            
            self.assertEqual(partner.department_id.code, dept_code)
            self.assertEqual(partner.country_id.code, country_code)
