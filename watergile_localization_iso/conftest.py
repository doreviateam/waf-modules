import pytest
import sys
from unittest.mock import MagicMock

# Mock Odoo pour les tests
class MockModel(MagicMock):
    _name = None
    _description = None
    AbstractModel = type('AbstractModel', (), {
        '__new__': lambda cls, *args, **kwargs: MagicMock()
    })

class MockOdoo:
    def __init__(self):
        self.models = MockModel()
        self.fields = MagicMock()
        self.api = MagicMock()
        self.addons = MagicMock()
    
    def _(self, text):
        return text

# Patch le module odoo pour les tests
sys.modules['odoo'] = MockOdoo()
sys.modules['odoo.addons'] = MockOdoo().addons

@pytest.fixture
def odoo_module():
    return 'watergile_localization_iso'