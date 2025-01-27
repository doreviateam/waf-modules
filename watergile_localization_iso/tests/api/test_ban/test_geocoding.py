import pytest
from unittest.mock import patch, MagicMock
from watergile_localization_iso.models.api.ban_api import BanAPIService, APIResponse

class TestBanGeocoding:
    """Tests des méthodes de géocodage du service BAN"""

    def test_reverse_geocode_success(self, ban_service, mock_reverse_response):
        """Test d'un géocodage inverse réussi"""
        # Configuration du mock
        ban_service.session.get.return_value.ok = True
        ban_service.session.get.return_value.json.return_value = mock_reverse_response

        # Test avec les coordonnées de Paris
        response = ban_service.reverse_geocode(
            lat=48.8566,
            lon=2.3522
        )

        # Vérifications
        assert response.success
        assert response.data == mock_reverse_response  # Vérification directe
        assert len(response.data["features"]) > 0
        feature = response.data["features"][0]
        assert feature["properties"]["city"] == "Paris"
        assert feature["properties"]["postcode"] == "75007"

        # Vérification de l'appel API
        ban_service.session.get.assert_called_once()
        call_args = ban_service.session.get.call_args
        assert call_args[0][0] == "https://api-adresse.data.gouv.fr/reverse"
        assert call_args[1]["params"]["lat"] == 48.8566
        assert call_args[1]["params"]["lon"] == 2.3522

    def test_reverse_geocode_invalid_coordinates(self, ban_service):
        """Test avec des coordonnées invalides"""
        # Test inchangé car il fonctionne déjà correctement
        response = ban_service.reverse_geocode(
            lat=91,  # Latitude invalide (> 90)
            lon=2.3522
        )
        assert not response.success
        assert response.error == ban_service.ERROR_MESSAGES['invalid_coordinates']

        response = ban_service.reverse_geocode(
            lat=48.8566,
            lon=181  # Longitude invalide (> 180)
        )
        assert not response.success
        assert response.error == ban_service.ERROR_MESSAGES['invalid_coordinates']

        # Vérifier qu'aucun appel API n'a été fait
        assert not ban_service.session.get.called

    def test_reverse_geocode_no_results(self, ban_service):
        """Test d'un géocodage inverse sans résultats"""
        # Configuration du mock pour simuler une réponse vide
        empty_response = {
            "type": "FeatureCollection",
            "features": []
        }
        ban_service.session.get.return_value.ok = True
        ban_service.session.get.return_value.json.return_value = empty_response

        response = ban_service.reverse_geocode(
            lat=0,
            lon=0  # Coordonnées en plein océan
        )

        assert response.success  # L'appel API est réussi
        assert response.data == empty_response
        assert len(response.data["features"]) == 0  # Mais pas de résultats

    def test_reverse_geocode_api_error(self, ban_service):
        """Test de la gestion des erreurs API"""
        # Simulation d'une erreur serveur
        ban_service.session.get.return_value.ok = False
        ban_service.session.get.return_value.status_code = 500
        ban_service.session.get.return_value.json.return_value = {
            "message": "Internal Server Error"
        }

        response = ban_service.reverse_geocode(
            lat=48.8566,
            lon=2.3522
        )
        assert not response.success
        assert response.error == ban_service.ERROR_MESSAGES['api_error']

        # Vérifier que l'appel API a été fait avec les bons paramètres
        ban_service.session.get.assert_called_once()
        call_args = ban_service.session.get.call_args
        assert call_args[1]["params"]["lat"] == 48.8566
        assert call_args[1]["params"]["lon"] == 2.3522