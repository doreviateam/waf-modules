"""
Script de migration WAF Core v17.0.1.0
"""
import logging
from odoo.tools import column_exists, table_exists

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Migration WAF Core"""
    if not version:
        return

    _logger.info("Début de la migration WAF Core v17.0.1.0")

    try:
        # 1. Configuration de base
        _setup_base_configuration(cr)
        # 2. Mise à jour des assets
        _update_assets(cr)
        # 3. Configuration des menus
        _setup_menus(cr)

    except Exception as e:
        _logger.error("Erreur durant la migration WAF Core: %s", str(e))
        raise

def _setup_base_configuration(cr):
    """Configuration des paramètres de base"""
    # Paramètres système
    params = [
        ('waf.theme.primary_color', '#875A7B'),
        ('waf.theme.secondary_color', '#00A09D'),
        ('waf.system.version', '17.0.1.0'),
    ]
    
    for key, value in params:
        cr.execute("""
            INSERT INTO ir_config_parameter (key, value)
            SELECT %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM ir_config_parameter WHERE key = %s
            )
        """, (key, value, key))

def _update_assets(cr):
    """Mise à jour des assets"""
    cr.execute("""
        UPDATE ir_asset
        SET path = REPLACE(path, '/waf_core/static/src/css/', '/waf_core/static/src/scss/')
        WHERE path LIKE '/waf_core/static/src/css/%'
    """)

def _setup_menus(cr):
    """Configuration des menus"""
    # Vérification et création du menu principal WAF
    cr.execute("""
        INSERT INTO ir_ui_menu (name, parent_id, sequence)
        SELECT 'menu_waf_root', NULL, 1
        WHERE NOT EXISTS (
            SELECT 1 FROM ir_ui_menu WHERE name = 'menu_waf_root'
        )
    """) 