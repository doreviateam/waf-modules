from unittest.mock import Mock, MagicMock
import re
import pytest

class APIResponse:
    def __init__(self, success: bool, data=None, error=None, raw_response=None):
        self.success = success
        self.data = data
        self.error = error
        self.raw_response = raw_response

class BanAPIService:
    def __init__(self):
        self._cache = {}
        self.ERROR_MESSAGES = {
            'empty_query': "La requête ne peut être vide",
            'invalid_postcode': "Le code postal est invalide",
            'invalid_coordinates': "Les coordonnées géographiques ne sont pas valides",
            'api_error': "Une erreur est survenue lors de l'appel à l'API"
        }

    def _get_base_url(self) -> str:
        return "https://api-adresse.data.gouv.fr"

class MockBanAPIService(BanAPIService):
    def __init__(self):
        super().__init__()
        self.session = Mock()
        self.session.get = Mock()

    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        key_parts = ["Base Adresse Nationale", prefix]
        filtered_kwargs = {k: v for k, v in sorted(kwargs.items()) if v is not None}
        key_parts.extend(f"{k}_{v}" for k, v in filtered_kwargs.items())
        return '_'.join(key_parts)

    def _validate_postcode(self, postcode: str) -> bool:
        if not postcode or not isinstance(postcode, str):
            return False
        return bool(re.match(r'^\d{5}$', postcode.strip()))
    
    #########################################################
    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        """Valide les coordonnées géographiques"""
        try:
            # Rejet explicite des chaînes de caractères
            if isinstance(lat, str) or isinstance(lon, str):
                return False
                
            lat, lon = float(lat), float(lon)
            return -90 <= lat <= 90 and -180 <= lon <= 180
        except (ValueError, TypeError):
            return False
        
    #########################################################
    def _validate_limit(self, limit: int) -> int:
        """Valide et normalise la limite de résultats"""
        try:
            # Pour les chaînes et les flottants, on convertit d'abord en float puis en int
            if isinstance(limit, (str, float)):
                try:
                    limit = int(float(limit))
                except ValueError:
                    return 5
            elif limit is None:
                return 5

            # Conversion en entier si ce n'est pas déjà fait
            limit = int(limit)

            # Application des limites min/max
            return min(max(1, limit), 100)
        except (ValueError, TypeError):
            return 5
    #########################################################

    def _validate_search_type(self, search_type: str) -> str:
        valid_types = ['municipality', 'locality', 'street', 'housenumber']
        return search_type if search_type in valid_types else 'municipality'


    def search_address(self, query: str, postcode: str = None, city: str = None,
                      limit: int = 5, search_type: str = 'municipality') -> APIResponse:
        if not query or not query.strip():
            return APIResponse(success=False, error=self.ERROR_MESSAGES['empty_query'])
        
        if postcode and not self._validate_postcode(postcode):
            return APIResponse(success=False, error=self.ERROR_MESSAGES['invalid_postcode'])

        params = {
            'q': query.strip(),
            'limit': self._validate_limit(limit),
            'type': self._validate_search_type(search_type)
        }
        if postcode:
            params['postcode'] = postcode.strip()
        if city:
            params['city'] = city.strip()

        cache_key = self._generate_cache_key('search', **params)
        if cache_key in self._cache:
            return self._cache[cache_key]

        response = self.session.get(f"{self._get_base_url()}/search", params=params)
        
        if not response.ok:
            result = APIResponse(success=False, error=self.ERROR_MESSAGES['api_error'])
        else:
            json_data = response.json.return_value
            result = APIResponse(
                success=True,
                data=json_data,
                raw_response=json_data
            )
        
        self._cache[cache_key] = result
        return result

    def reverse_geocode(self, lat: float, lon: float, limit: int = 5, 
                       type: str = None) -> APIResponse:
        if not self._validate_coordinates(lat, lon):
            return APIResponse(success=False, error=self.ERROR_MESSAGES['invalid_coordinates'])

        params = {
            'lat': lat,
            'lon': lon,
            'limit': self._validate_limit(limit),
            'type': self._validate_search_type(type) if type else None
        }

        cache_key = self._generate_cache_key('reverse', **params)
        if cache_key in self._cache:
            return self._cache[cache_key]

        response = self.session.get(f"{self._get_base_url()}/reverse", params=params)
        
        if not response.ok:
            result = APIResponse(success=False, error=self.ERROR_MESSAGES['api_error'])
        else:
            json_data = response.json.return_value
            result = APIResponse(
                success=True,
                data=json_data,
                raw_response=json_data
            )
        
        self._cache[cache_key] = result
        return result

@pytest.fixture
def ban_service():
    return MockBanAPIService()

@pytest.fixture
def mock_search_response():
    return {
        "type": "FeatureCollection",
        "version": "draft",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [2.3522, 48.8566]
            },
            "properties": {
                "label": "20 Avenue de Ségur 75007 Paris",
                "postcode": "75007",
                "city": "Paris"
            }
        }]
    }

@pytest.fixture
def mock_reverse_response():
    return {
        "type": "FeatureCollection",
        "version": "draft",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [2.3522, 48.8566]
            },
            "properties": {
                "label": "20 Avenue de Ségur 75007 Paris",
                "score": 0.98,
                "type": "housenumber",
                "name": "20 Avenue de Ségur",
                "postcode": "75007",
                "city": "Paris"
            }
        }]
    }