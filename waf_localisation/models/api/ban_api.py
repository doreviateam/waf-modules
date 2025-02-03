from typing import Optional, Dict, Any, List, Union
from .base_api import BaseAPIService, APIResponse
import logging

_logger = logging.getLogger(__name__)


class BanAPIService(BaseAPIService):
    """Service API pour la Base Adresse Nationale (BAN)"""

    SEARCH_TYPES = {'municipality', 'housenumber', 'street'}
    MAX_LIMIT = 100

    ERROR_MESSAGES = {
        'empty_query': 'La requête ne peut être vide',
        'invalid_coordinates': 'Les coordonnées géographiques ne sont pas valides',
        'invalid_postcode': 'Le code postal est invalide',
        'invalid_city': 'Le nom de la ville est invalide'
    }

    @property
    def name(self) -> str:
        return 'Base Adresse Nationale'

    def get_base_url(self) -> str:
        return 'https://api-adresse.data.gouv.fr'

    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        if isinstance(lat, str) or isinstance(lon, str):
            return False
        try:
            lat, lon = float(lat), float(lon)
            return -90 <= lat <= 90 and -180 <= lon <= 180
        except (ValueError, TypeError):
            return False

    def _validate_limit(self, limit: int) -> int:
        """Valide et normalise la limite de résultats"""
        try:
            if isinstance(limit, (str, float)):
                try:
                    limit = int(float(limit))
                except ValueError:
                    return 5
            elif limit is None:
                return 5

            limit = int(limit)
            return min(max(1, limit), 100)
        except (ValueError, TypeError):
            return 5

    def _validate_search_type(self, search_type: Optional[str]) -> str:
        """Validation du type de recherche"""
        return search_type if search_type in self.SEARCH_TYPES else 'municipality'

    def _validate_postcode(self, postcode: Optional[str]) -> bool:
        """Validation du format du code postal"""
        if not postcode:
            return True
        return bool(postcode.strip().isdigit() and len(postcode.strip()) == 5)

    def search_address(
        self,
        query: str,
        postcode: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 5,
        search_type: str = 'municipality',
    ) -> APIResponse:
        """Recherche d'une adresse"""
        _logger.info(f"""
        ====== BAN API REQUEST ======
        Query: {query}
        Postcode: {postcode}
        City: {city}
        Type: {search_type}
        ============================""")

        if not query or not query.strip():
            return APIResponse(success=False, error=self.ERROR_MESSAGES['empty_query'])

        if postcode and not self._validate_postcode(postcode):
            return APIResponse(success=False, error=self.ERROR_MESSAGES['invalid_postcode'])

        # Déterminer automatiquement le type de recherche
        if query.strip() == city:
            actual_type = 'municipality'
        elif any(c.isdigit() for c in query):
            actual_type = 'housenumber'
        else:
            actual_type = 'street'

        params = {
            'q': query.strip(),
            'limit': self._validate_limit(limit),
            'type': self._validate_search_type(actual_type)  # Utiliser le type déterminé
        }

        if postcode:
            params['postcode'] = postcode.strip()
        if city:
            params['city'] = city.strip()

        _logger.info(f"Final params: {params}")
        
        # Utiliser le cache pour cette requête
        cache_key = self._generate_cache_key('address', **params)
        response = self.get_cached_request(cache_key, '/search', **params)
        
        if response.success and response.data:
            _logger.info(f"""
            ====== BAN API RESPONSE ======
            Success: {response.success}
            Features: {len(response.data.get('features', []))}
            First feature: {response.data.get('features', [{}])[0] if response.data.get('features') else 'No features'}
            ==============================""")
        else:
            _logger.warning(f"""
            ====== BAN API ERROR ======
            Success: {response.success}
            Error: {response.error}
            ===========================""")

        return response

    def reverse_geocode(
        self,
        lat: float,
        lon: float,
        limit: int = 5,
        type: Optional[str] = None
    ) -> APIResponse:
        """Rétro-codage d'une coordonnée géographique"""
        if not self._validate_coordinates(lat, lon):
            return APIResponse(
                success=False,
                error=self.ERROR_MESSAGES['invalid_coordinates']
            )

        params = {
            'lat': lat,
            'lon': lon,
            'limit': self._validate_limit(limit),
            'type': self._validate_search_type(type) if type else None
        }

        return self._make_request('reverse', params=params)

    def search_postcode(self, postcode: str, limit: int=5) -> APIResponse:
        """Recherche d'un code postal"""
        if not self._validate_postcode(postcode):
            return APIResponse(success=False, error=self.ERROR_MESSAGES['invalid_postcode'])

        params = {
            'q': postcode.strip(),
            'type': 'municipality',
            'limit': self._validate_limit(limit)
        }
        cache_key = self._generate_cache_key('postcode', **params)
        return self.get_cached_request(cache_key, '/search', **params)

    def search_city(self, city: str, limit: int=5) -> APIResponse:
        """Recherche d'une ville"""
        params = {
            'q': city.strip(),
            'type': 'municipality',
            'limit': self._validate_limit(limit)
        }
        cache_key = self._generate_cache_key('city', **params)
        return self.get_cached_request(cache_key, '/search', **params)

    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Génération d'une clé de cache"""
        key_parts = [self.name, prefix]
        for k, v in sorted(kwargs.items()):
            if v:
                key_parts.append(f"{k}_{v}")
        return '_'.join(key_parts)

    def _get_cached_response(self, cache_key: str, endpoint: str, **kwargs) -> APIResponse:
        """Récupération d'une réponse en cache"""
        return self.get_cached_request(cache_key, endpoint, **kwargs)
