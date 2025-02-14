import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    _logger.info("=== DÉBUT POST-MIGRATION WAF CONTACTS ===")
    cr.execute("SELECT 1")  # Simple requête pour test
    _logger.info("=== FIN POST-MIGRATION WAF CONTACTS ===") 