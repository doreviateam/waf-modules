import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Migration WAF Localisation"""
    _logger.warning("=== DÉBUT PRE-MIGRATION WAF LOCALISATION (version: %s) ===", version)
    _logger.warning("Version actuelle : %s", version)
    
    if not version:
        _logger.warning("Première installation, pas de migration nécessaire")
        return

    # Vérification de l'existence de la table
    cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'res_partner')")
    table_exists = cr.fetchone()[0]
    _logger.warning("La table res_partner existe : %s", table_exists)

    _logger.warning("=== FIN PRE-MIGRATION WAF LOCALISATION ===")
