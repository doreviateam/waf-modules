import pytest
from unittest.mock import patch, MagicMock
from watergile_localization_iso.models.api.ban_api import BanAPIService, APIResponse

class TestBanSearch:
    """Tests des méthodes de recherche du service BAN"""

    def test_search_address_success(self, ban_service, mock_search_response):
        """Test d'une recherche d'adresse réussie"""
        # Configuration du mock
        ban_service.session.get.return_value.ok = True
        ban_service.session.get.return_value.json.return_value = mock_search_response

        # Test
        response = ban_service.search_address(
            query="20 Avenue de Ségur",
            postcode="75007",
            city="Paris"
        )

        # Vérifications
        assert response.success
        assert response.data == mock_search_response
        assert len(response.data["features"]) > 0
        feature = response.data["features"][0]
        assert feature["properties"]["postcode"] == "75007"
        assert feature["properties"]["city"] == "Paris"

        # Vérification de l'appel API
        ban_service.session.get.assert_called_once()
        call_args = ban_service.session.get.call_args
        assert call_args[0][0] == "https://api-adresse.data.gouv.fr/search"
        assert call_args[1]["params"]["q"] == "20 Avenue de Ségur"
        assert call_args[1]["params"]["postcode"] == "75007"
        assert call_args[1]["params"]["city"] == "Paris"

    def test_search_address_empty_query(self, ban_service):
        """Test d'une recherche avec une requête vide"""
        response = ban_service.search_address(query="")
        assert not response.success
        assert response.error == ban_service.ERROR_MESSAGES['empty_query']
        
        # Vérifier qu'aucun appel API n'a été fait
        assert not ban_service.session.get.called

    def test_search_address_invalid_postcode(self, ban_service):
        """Test d'une recherche avec un code postal invalide"""
        response = ban_service.search_address(
            query="20 Avenue de Ségur",
            postcode="7500"  # Code postal invalide
        )
        assert not response.success
        assert response.error == ban_service.ERROR_MESSAGES['invalid_postcode']
        
        # Vérifier qu'aucun appel API n'a été fait
        assert not ban_service.session.get.called

    def test_search_address_api_error(self, ban_service):
        """Test de la gestion des erreurs API"""
        # Simulation d'une erreur API
        ban_service.session.get.return_value.ok = False
        ban_service.session.get.return_value.status_code = 404
        ban_service.session.get.return_value.json.return_value = {"message": "Not found"}

        response = ban_service.search_address(query="Adresse inexistante")
        assert not response.success
        assert response.error == ban_service.ERROR_MESSAGES['api_error']

        # Vérifier que l'appel API a été fait
        ban_service.session.get.assert_called_once()

    def test_search_address_overseas(self, ban_service):
        """Test d'une recherche d'adresse en Outre-mer"""
        # Simulation réponse API pour une adresse en Guadeloupe
        mock_response = {
            "type": "FeatureCollection",
            "version": "draft",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-61.380597, 16.223658]
                    },
                    "properties": {
                        "label": "3 Chemin Poirier 97180 Sainte-Anne",
                        "score": 0.9876543210,
                        "housenumber": "3",
                        "street": "Chemin Poirier",
                        "postcode": "97180",
                        "city": "Sainte-Anne",
                        "context": "971, Guadeloupe",
                        "type": "housenumber",
                        "importance": 0.6357
                    }
                }
            ]
        }

        # Configuration du mock
        ban_service.session.get.return_value.ok = True
        ban_service.session.get.return_value.json.return_value = mock_response

        # Test
        response = ban_service.search_address(
            query="3 chemin Poirier",
            postcode="97180",
            city="Sainte Anne"
        )

        # Vérifications
        assert response.success
        assert response.data == mock_response
        
        feature = response.data["features"][0]
        assert feature["properties"]["postcode"] == "97180"
        assert feature["properties"]["city"] == "Sainte-Anne"
        assert "Guadeloupe" in feature["properties"]["context"]

        # Vérification des coordonnées
        coordinates = feature["geometry"]["coordinates"]
        assert -62 < coordinates[0] < -61  # Longitude Guadeloupe
        assert 16 < coordinates[1] < 17    # Latitude Guadeloupe

        # Vérification de l'appel API
        ban_service.session.get.assert_called_once()
        call_args = ban_service.session.get.call_args
        assert call_args[1]["params"]["q"] == "3 chemin Poirier"
        assert call_args[1]["params"]["postcode"] == "97180"
        assert call_args[1]["params"]["city"] == "Sainte Anne"