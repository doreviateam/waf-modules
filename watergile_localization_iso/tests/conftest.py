# /tests/conftest.py
import pytest
from unittest.mock import Mock
from watergile_localization_iso.models.api.ban_api import BanAPIService, APIResponse

@pytest.fixture(scope='session')
def mock_api_response():
    """Fixture globale pour les réponses API"""
    mock = Mock()
    mock.ok = True
    mock.status_code = 200
    return mock