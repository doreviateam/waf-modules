from odoo.tests import common



class TestSaleTimesheet(common.TestSaleTimesheet):
    def setUp(self):
        super().setUp()
        # Ajouter le contexte de test
        self.env = self.env(context=dict(self.env.context, test_mode=True)) 