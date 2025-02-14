import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Post-migration WAF Localisation"""
    _logger.warning("=== DÉBUT POST-MIGRATION WAF LOCALISATION (version: %s) ===", version)
    if not version:
        return
    _logger.warning("=== FIN POST-MIGRATION WAF LOCALISATION ===")
