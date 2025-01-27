import pytest
from unittest.mock import patch, call, MagicMock
from watergile_localization_iso.models.api.ban_api import BanAPIService, APIResponse

class TestBanCache:
    """Tests du système de cache du service BAN"""

    def test_cache_key_generation(self, ban_service):
        """Test de la génération des clés de cache"""
        # Inchangé car fonctionne déjà

    def test_cache_reuse(self, ban_service, mock_search_response):
        """Test de la réutilisation du cache"""
        # Configuration du mock
        ban_service.session.get.return_value.ok = True
        ban_service.session.get.return_value.json.return_value = mock_search_response

        # Première recherche
        response1 = ban_service.search_address(
            query="20 Avenue de Ségur",
            postcode="75007"
        )
        assert response1.success
        assert response1.data == mock_search_response

        # Même recherche, devrait utiliser le cache
        response2 = ban_service.search_address(
            query="20 Avenue de Ségur",
            postcode="75007"
        )
        assert response2.success
        assert response2.data == mock_search_response

        # Vérification que l'API n'a été appelée qu'une seule fois
        assert ban_service.session.get.call_count == 1

    def test_different_queries_different_cache(self, ban_service, mock_search_response):
        """Test que différentes requêtes utilisent différentes clés de cache"""
        # Configuration du mock
        ban_service.session.get.return_value.ok = True
        ban_service.session.get.return_value.json.return_value = mock_search_response

        # Deux recherches différentes
        response1 = ban_service.search_address(
            query="20 Avenue de Ségur", 
            postcode="75007"
        )
        response2 = ban_service.search_address(
            query="15 Rue de Rivoli", 
            postcode="75004"
        )

        # Vérification que l'API a été appelée deux fois
        assert ban_service.session.get.call_count == 2
        
        # Vérifier que les appels sont différents
        calls = ban_service.session.get.call_args_list
        assert calls[0] != calls[1]
        
        # Vérifier les paramètres des appels
        params1 = calls[0][1]['params']
        params2 = calls[1][1]['params']
        assert params1['q'] == "20 Avenue de Ségur"
        assert params1['postcode'] == "75007"
        assert params2['q'] == "15 Rue de Rivoli"
        assert params2['postcode'] == "75004"

    def test_cache_key_consistency(self, ban_service):
        """Test de la cohérence des clés de cache"""
        # Inchangé car fonctionne déjà

    def test_cache_with_none_values(self, ban_service):
        """Test de la génération de clé avec des valeurs None"""
        # Inchangé car fonctionne déjà