import pytest
from watergile_localization_iso.models.api.ban_api import BanAPIService, APIResponse

class TestBanValidation:
    """Tests des méthodes de validation du service BAN"""

    def test_validate_coordinates(self, ban_service):
        """Test de la validation des coordonnées géographiques"""
        # Cas valides
        valid_coordinates = [
            (48.8566, 2.3522),    # Paris
            (0, 0),               # Point zéro
            (-90, 180),           # Limites minimales/maximales
            (90, -180),           # Autres limites
            (45.5, 45.5),         # Valeurs identiques
            (-45.5, -45.5)        # Valeurs négatives identiques
        ]
        for lat, lon in valid_coordinates:
            assert ban_service._validate_coordinates(lat, lon), f"Devrait accepter lat={lat}, lon={lon}"

        # Cas invalides
        invalid_coordinates = [
            (91, 0),              # Latitude trop grande
            (-91, 0),             # Latitude trop petite
            (0, 181),             # Longitude trop grande
            (0, -181),            # Longitude trop petite
            ("invalid", 0),       # Type invalide pour latitude
            (0, "invalid"),       # Type invalide pour longitude
            (None, 0),            # None pour latitude
            (0, None),            # None pour longitude
            ("", ""),             # Chaînes vides
            ("45.5", "45.5")      # Chaînes numériques (devraient être des nombres)
        ]
        for lat, lon in invalid_coordinates:
            assert not ban_service._validate_coordinates(lat, lon), f"Devrait rejeter lat={lat}, lon={lon}"

    def test_validate_postcode(self, ban_service):
        """Test de la validation des codes postaux"""
        # Cas valides
        valid_postcodes = [
            "75007",     # Paris
            "13100",     # Aix-en-Provence
            "97100",     # Guadeloupe
            "98000",     # Monaco
            "20000"      # Corse
        ]
        for postcode in valid_postcodes:
            assert ban_service._validate_postcode(postcode), f"Devrait accepter {postcode}"

        # Cas invalides
        invalid_postcodes = [
            "7500",      # Trop court
            "750007",    # Trop long
            "ABCDE",     # Non numérique
            "",          # Vide
            None,        # None
            "12.34",     # Décimal
            "12 34",     # Espace
            "-1234",     # Négatif
            "0"          # Un seul chiffre
        ]
        for postcode in invalid_postcodes:
            assert not ban_service._validate_postcode(postcode), f"Devrait rejeter {postcode}"

    def test_validate_limit(self, ban_service):
        """Test de la validation des limites de résultats"""
        # Test des valeurs normales
        assert ban_service._validate_limit(5) == 5           # Valeur normale
        assert ban_service._validate_limit(1) == 1           # Minimum exact
        assert ban_service._validate_limit(100) == 100       # Maximum exact

        # Test des valeurs limites
        assert ban_service._validate_limit(0) == 1           # Sous le minimum
        assert ban_service._validate_limit(-1) == 1          # Négatif
        assert ban_service._validate_limit(200) == 100       # Au-dessus du maximum

        # Test des types différents
        assert ban_service._validate_limit("10") == 10       # String valide
        assert ban_service._validate_limit("invalid") == 5   # String invalide
        assert ban_service._validate_limit(None) == 5        # None
        assert ban_service._validate_limit(3.14) == 3        # Float
        assert ban_service._validate_limit("3.14") == 3      # String float

    def test_validate_search_type(self, ban_service):
        """Test de la validation des types de recherche"""
        # Types valides
        valid_types = ['municipality', 'locality', 'street', 'housenumber']
        for search_type in valid_types:
            assert ban_service._validate_search_type(search_type) == search_type

        # Types invalides
        invalid_types = [
            'invalid',
            '',
            None,
            123,
            'MUNICIPALITY',  # Casse différente
            ' municipality ' # Espaces
        ]
        for search_type in invalid_types:
            assert ban_service._validate_search_type(search_type) == 'municipality'