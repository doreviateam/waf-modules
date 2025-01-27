# /tests/api/conftest.py
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_responses():
    """Fixture pour les réponses mockées"""
    return {
        'search': {'features': []},
        'geocode': {'features': []}
    }