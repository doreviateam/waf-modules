"""
Script de migration WAF Contacts v17.0.1.0
"""
import logging
from odoo.tools import column_exists, table_exists

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Migration WAF Contacts"""
    _logger.warning("=== DÉBUT PRE-MIGRATION WAF CONTACTS (version: %s) ===", version)
    if not version:
        _logger.warning("Première installation, pas de migration nécessaire")
        return

    _logger.info("Début de la migration WAF Contacts v17.0.1.0")

    try:
        # 1. Structure des régions
        _setup_region_structure(cr)
        # 2. Mise à jour des partenaires
        _update_partner_structure(cr)
        # 3. Configuration des droits
        _setup_access_rights(cr)

    except Exception as e:
        _logger.error("Erreur durant la migration WAF Contacts: %s", str(e))
        raise

def _setup_region_structure(cr):
    """Création/Mise à jour de la structure des régions"""
    if not table_exists(cr, 'res_country_state_region'):
        cr.execute("""
            CREATE TABLE res_country_state_region (
                id serial PRIMARY KEY,
                name varchar NOT NULL,
                code varchar NOT NULL,
                country_id integer REFERENCES res_country(id) ON DELETE CASCADE,
                active boolean DEFAULT true,
                create_uid integer REFERENCES res_users(id),
                create_date timestamp without time zone DEFAULT now(),
                write_uid integer REFERENCES res_users(id),
                write_date timestamp without time zone DEFAULT now()
            )
        """)

        # Index pour les performances
        cr.execute("""
            CREATE INDEX IF NOT EXISTS region_country_id_idx 
            ON res_country_state_region (country_id);
            CREATE UNIQUE INDEX IF NOT EXISTS region_code_unique_idx 
            ON res_country_state_region (code);
        """)

def _update_partner_structure(cr):
    """Mise à jour de la structure des partenaires"""
    # Ajout des colonnes pour les régions si elles n'existent pas
    if not column_exists(cr, 'res_partner', 'region_id'):
        cr.execute("""
            ALTER TABLE res_partner 
            ADD COLUMN region_id integer REFERENCES res_country_state_region(id);
            CREATE INDEX IF NOT EXISTS partner_region_id_idx 
            ON res_partner (region_id);
        """)

    # Ajout des colonnes pour les départements
    if not column_exists(cr, 'res_country_state', 'region_id'):
        cr.execute("""
            ALTER TABLE res_country_state 
            ADD COLUMN region_id integer REFERENCES res_country_state_region(id);
            CREATE INDEX IF NOT EXISTS state_region_id_idx 
            ON res_country_state (region_id);
        """)

def _setup_access_rights(cr):
    """Configuration des droits d'accès"""
    # Droits d'accès pour les régions
    access_rights = [
        ('access_region_user', 'res.country.state.region', 'group_user', 1, 0, 0, 0),
        ('access_region_manager', 'res.country.state.region', 'group_partner_manager', 1, 1, 1, 1)
    ]

    for access in access_rights:
        cr.execute("""
            INSERT INTO ir_model_access (
                name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink
            )
            SELECT 
                %s,
                (SELECT id FROM ir_model WHERE model = %s),
                (SELECT id FROM res_groups WHERE name = %s),
                %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM ir_model_access WHERE name = %s
            )
        """, (access[0], access[1], access[2], access[3], access[4], access[5], access[6], access[0]))

    _logger.info("Migration WAF Contacts terminée avec succès") 