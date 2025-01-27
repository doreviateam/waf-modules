from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import datetime
from odoo.fields import Date, Datetime

class TestDispatch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create a product for testing
        cls.product = cls.env['product.product'].create({
            'name': 'TPE ICT250',
            'type': 'product',
            'invoice_policy': 'order',
        })
        
        # Create main company first
        cls.company_main = cls.env['res.partner'].create({
            'name': 'Maison Mère Test',
            'is_company': True,
        })

    def setUp(self):
        super().setUp()
        
        # Create partner
        self.partner = self.env['res.partner'].create({
            'name': 'Crédit Mutuel de l\'Hérault',
            'is_company': True,
        })
        
        # Create delivery address after partner exists
        self.delivery_address = self.env['res.partner'].create({
            'name': 'Delivery Address',
            'type': 'delivery',
            'parent_id': self.partner.id,
        })
        
        # Create addresses for tests
        self.address1 = self.env['res.partner'].create({
            'name': 'Address 1',
            'type': 'delivery',
            'parent_id': self.partner.id,
        })
        
        self.address2 = self.env['res.partner'].create({
            'name': 'Address 2',
            'type': 'delivery',
            'parent_id': self.partner.id,
        })
        
        # Create sale order after partner exists
        self.sale_order = self.env['sale.order'].with_context(skip_preso_check=True).create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
            })]
        })

    def test_initial_quantity(self):
        """Test de la quantité initiale disponible"""
        # Vérifier que la quantité initiale est bien celle de la ligne de commande
        dispatch = self.env['pre.sale.order.line'].create({
            'sale_order_id': self.sale_order.id,
            'product_id': self.product.id,
            'partner_id': self.partner.id,
            'delivery_address_id': self.delivery_address.id,
            'quantity': 0,
        })
        # La quantité disponible doit être égale à la quantité de la ligne de commande
        self.assertEqual(dispatch.available_quantity, 10.0)

    def test_remaining_quantity(self):
        """Test de la quantité restante après un dispatch"""
        # Premier dispatch de 5 unités
        dispatch1 = self.env['pre.sale.order.line'].create({
            'sale_order_id': self.sale_order.id,
            'product_id': self.product.id,
            'partner_id': self.partner.id,
            'delivery_address_id': self.delivery_address.id,
            'quantity': 5,
        })

        # Vérifier la quantité disponible pour un nouveau dispatch
        dispatch2 = self.env['pre.sale.order.line'].create({
            'sale_order_id': self.sale_order.id,
            'product_id': self.product.id,
            'partner_id': self.partner.id,
            'delivery_address_id': self.delivery_address.id,
            'quantity': 0,
        })
        self.assertEqual(dispatch2.available_quantity, 5.0)

    def test_over_dispatch(self):
        """Test de dispatch avec une quantité excessive"""
        # Premier dispatch de 7 unités
        dispatch1 = self.env['pre.sale.order.line'].create({
            'sale_order_id': self.sale_order.id,
            'product_id': self.product.id,
            'partner_id': self.partner.id,
            'delivery_address_id': self.delivery_address.id,
            'quantity': 7,
        })

        # Tenter un second dispatch de 5 unités (devrait échouer car 7 + 5 > 10)
        with self.assertRaises(ValidationError):
            self.env['pre.sale.order.line'].create({
                'sale_order_id': self.sale_order.id,
                'product_id': self.product.id,
                'partner_id': self.partner.id,
                'delivery_address_id': self.delivery_address.id,
                'quantity': 5,
            })

    def test_movement_creation(self):
        """Test de la création des mouvements"""
        dispatch = self.env['pre.sale.order.line'].create({
            'sale_order_id': self.sale_order.id,
            'product_id': self.product.id,
            'partner_id': self.partner.id,
            'delivery_address_id': self.delivery_address.id,
            'quantity': 5,
        })

        # Vérifier la création du mouvement
        movement = self.env['pre.sale.order.movements'].search([
            ('sale_order_id', '=', self.sale_order.id),
            ('product_id', '=', self.product.id),
            ('pre_sale_order_line_id', '=', dispatch.id),
        ], order='create_date DESC', limit=1)

        self.assertTrue(movement)
        self.assertEqual(movement.credit, 5.0)
        self.assertEqual(movement.running_balance, -5.0)

    def test_is_preso_reset(self):
        """Test la réinitialisation des champs quand is_preso passe à False"""
        # Créer une commande avec is_preso=True
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'is_preso': True,
        })
        
        # Créer une ligne de commande pour avoir une quantité disponible
        order_line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'price_unit': 100,
        })
        
        # Ajouter une ligne de préparation
        dispatch = self.env['pre.sale.order.line'].create({
            'sale_order_id': order.id,
            'product_id': self.product.id,
            'quantity': 5,
            'partner_id': self.partner.id,
            'delivery_address_id': self.partner.id,
        })
        
        # Vérifier que les données sont présentes
        self.assertTrue(order.pre_sale_order_line_ids)
        
        # Passer is_preso à False
        order.is_preso = False
        
        # Vérifier que les champs sont réinitialisés
        self.assertFalse(order.pre_sale_order_line_ids)
        self.assertEqual(order.delivery_status, 'none')

    def test_is_preso_locked(self):
        """Test le verrouillage des lignes en mode préparation"""
        # Créer une commande
        order = self.sale_order
        
        # Activer le mode préparation
        order.is_preso = True
        
        # Tentative de modification de la quantité
        with self.assertRaises(ValidationError):
            order.order_line.write({
                'product_uom_qty': 20
            })

    def test_is_preso_keep_data(self):
        """Test que les données sont conservées quand is_preso reste à True"""
        # Créer une commande avec is_preso=True
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'is_preso': True,
        })
        
        # Créer une ligne de commande pour avoir une quantité disponible
        order_line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'price_unit': 100,
        })
        
        # Ajouter une ligne de préparation
        dispatch = self.env['pre.sale.order.line'].create({
            'sale_order_id': order.id,
            'product_id': self.product.id,
            'quantity': 5,
            'partner_id': self.partner.id,
            'delivery_address_id': self.partner.id,
        })
        
        # Modifier un autre champ de la commande
        order.note = "Test note"
        
        # Vérifier que les données de préparation sont toujours présentes
        self.assertTrue(order.pre_sale_order_line_ids)
        self.assertEqual(len(order.pre_sale_order_line_ids), 1)
        self.assertEqual(order.pre_sale_order_line_ids[0].quantity, 5)

    def test_remaining_quantity_display(self):
        dispatch1 = self.env['pre.sale.order.line'].create({
            'sale_order_id': self.sale_order.id,
            'product_id': self.product.id,
            'quantity': 4,
            'delivery_date': Date.today(),
            'delivery_address_id': self.delivery_address.id,
        })
        self.assertEqual(dispatch1.remaining_quantity, 6)

        dispatch2 = self.env['pre.sale.order.line'].create({
            'sale_order_id': self.sale_order.id,
            'product_id': self.product.id,
            'quantity': 3,
            'delivery_date': Date.today(),
            'delivery_address_id': self.delivery_address.id,
        })
        self.assertEqual(dispatch2.remaining_quantity, 3)

    def test_confirm_preso_order(self):
        """Test la confirmation d'une commande en mode préparation"""
        # Création d'une commande avec une ligne
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
            })]
        })
        
        # Test confirmation standard (sans préparation)
        order.is_preso = False  # S'assurer que is_preso est False
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        
        # Nouvelle commande avec préparation
        order2 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
            })]
        })
        
        # Activation du mode préparation
        order2.is_preso = True
        
        # Tentative de confirmation sans dispatch
        with self.assertRaises(ValidationError):
            order2.action_confirm()
            
        # Création du dispatch
        self.env['pre.sale.order.line'].create({
            'sale_order_id': order2.id,
            'product_id': self.product.id,
            'quantity': 10,
            'delivery_date': Datetime.now(),
            'delivery_address_id': self.partner.id,
        })
        
        # Confirmation de la commande
        order2.action_confirm()
        
        # Vérifications
        self.assertEqual(order2.state, 'sale')
        self.assertFalse(order2.is_preso)
        self.assertTrue(all(line.state == 'confirmed' for line in order2.pre_sale_order_line_ids))
