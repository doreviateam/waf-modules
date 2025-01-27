from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import requests
from time import sleep
import logging

_logger = logging.getLogger(__name__)

@dataclass
class APIResponse:
    """Structure commune pour les réponses des API"""
    success: bool
    data: dict = None
    error: str = None
    raw_response: Optional[Dict[str, Any]] = None


class BaseAPIService(ABC):
    """Classe abstraite de base pour les services API"""

    def __init__(self, timeout: int = 10, retry_attempts: int = 3, retry_delay: int = 1, backoff_factor: int = 2.0):
        """Initialisation du service API"""
        self.session = requests.Session()
        self.base_url = self.get_base_url()
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self._setup_session()
    
    def _setup_session(self) -> None:
        """Configuration de la session HTTP"""
        self.session.headers.update({
            'User-Agent': f'{self.name}/1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom du service API"""
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        """URL de base du service API"""
        pass

    def _validate_params(self, params: Optional[Dict[str, Any]]) -> bool:
        """Validation des paramètres"""
        if params is None:
            return True
        try:
            return all(isinstance(k, str) and not str(v).strip() == '' and v is not None for k, v in params.items())
        except Exception as e:
            _logger.error(f"Erreur de validation des paramètres pour {self.name} : {str(e)}")
            return False 
                
    def _make_request(self, endpoint: str, method: str = 'GET', params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Effectue une requête API avec gestion des erreurs"""
        if not self._validate_params(params):
            return APIResponse(success=False, error="Paramètres invalides")
        
        for attempt in range(self.retry_attempts):
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            try:                
                response = self.session.request(method=method, url=url, params=params, json=data, headers=headers, timeout=self.timeout)
                
                if response.ok:
                    return APIResponse(success=response.ok, data=response.json(), raw_response=response.json())
                
                if response.status_code in {401, 403, 404}:
                    return self._handle_error(response)
                
            except requests.exceptions.RequestException as e:
                if attempt == self.retry_attempts - 1:
                    _logger.error(f"Echec de la requête API {self.name} - {method} {url} : {str(e)} apres {self.retry_attempts} tentatives")
                    return APIResponse(success=False, error=f"Erreur API : {str(e)}")

                waite_time = self.retry_delay * (self.backoff_factor ** attempt)
                _logger.warning(f"Tentative {attempt + 1}/{self.retry_attempts} echouée - {waite_time} secondes de pause")
                sleep(waite_time)
        
    def _handle_error(self, response: requests.Response) -> APIResponse:
        """Gestion des erreurs de réponse"""
        error_mapping = {
            400: "Requête invalide",
            401: "Non autorisé",
            403: "Accès refusé",
            404: "Ressource non trouvée",
            429: "Trop de requêtes",
            500: "Erreur interne du serveur",
            502: "Service indisponible",
            503: "Service temporairement indisponible",
            504: "Délai de requête expiré",
        }

        error_message = error_mapping.get(response.status_code, f"Erreur API: {response.status_code}")

        try:
            error_details = response.json()
            error_message = f"{error_message}: {error_details.get('message', 'Autre erreur')}"
        except Exception as e:
            _logger.error(f"Erreur API: {self.name} - {error_message} : {str(e)}")
        
        return APIResponse(success=False, error=error_message, raw_response=response.text)
    
    @lru_cache(maxsize=128)
    def _cached_request(self, cache_key: str, endpoint: str, **params) -> APIResponse:
        """Requête API avec cache"""
        return self._make_request(endpoint, params=params)

    def get_cached_request(self, cache_key: str, endpoint: str, **params) -> APIResponse:
        """Récupération de la requête API avec cache"""
        return self._cached_request(cache_key, endpoint, **params)
    
    def __del__(self):
        """Ferme la session HTTP"""
        if hasattr(self, 'session'):
            self.session.close()
    
