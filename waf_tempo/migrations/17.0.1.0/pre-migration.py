"""
Script de migration WAF Tempo v17.0.1.0
"""
import logging
from odoo.tools import column_exists, table_exists

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Migration WAF Tempo"""
    if not version:
        return

    _logger.info("Début de la migration WAF Tempo v17.0.1.0")

    try:
        # 1. Structure des calendriers
        _setup_calendar_structure(cr)
        # 2. Structure des jours fériés
        _setup_holiday_structure(cr)
        # 3. Configuration des périodes
        _setup_period_structure(cr)
        # 4. Configuration des droits
        _setup_access_rights(cr)

    except Exception as e:
        _logger.error("Erreur durant la migration WAF Tempo: %s", str(e))
        raise

def _setup_calendar_structure(cr):
    """Création/Mise à jour de la structure des calendriers"""
    if not table_exists(cr, 'calendar_region'):
        cr.execute("""
            CREATE TABLE calendar_region (
                id serial PRIMARY KEY,
                name varchar NOT NULL,
                code varchar NOT NULL,
                country_code varchar(2) NOT NULL,
                active boolean DEFAULT true,
                workdays varchar DEFAULT '1,2,3,4,5',
                create_uid integer REFERENCES res_users(id),
                create_date timestamp without time zone DEFAULT now(),
                write_uid integer REFERENCES res_users(id),
                write_date timestamp without time zone DEFAULT now()
            )
        """)

        # Index pour les performances
        cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS calendar_region_code_unique_idx 
            ON calendar_region (code);
            CREATE INDEX IF NOT EXISTS calendar_region_country_code_idx 
            ON calendar_region (country_code);
        """)

def _setup_holiday_structure(cr):
    """Création/Mise à jour de la structure des jours fériés"""
    if not table_exists(cr, 'calendar_holiday'):
        cr.execute("""
            CREATE TABLE calendar_holiday (
                id serial PRIMARY KEY,
                name varchar NOT NULL,
                date date NOT NULL,
                region_id integer REFERENCES calendar_region(id) ON DELETE CASCADE,
                type varchar DEFAULT 'fixed',
                active boolean DEFAULT true,
                create_uid integer REFERENCES res_users(id),
                create_date timestamp without time zone DEFAULT now(),
                write_uid integer REFERENCES res_users(id),
                write_date timestamp without time zone DEFAULT now(),
                UNIQUE(date, region_id)
            )
        """)

        # Index pour les performances
        cr.execute("""
            CREATE INDEX IF NOT EXISTS calendar_holiday_region_id_idx 
            ON calendar_holiday (region_id);
            CREATE INDEX IF NOT EXISTS calendar_holiday_date_idx 
            ON calendar_holiday (date);
        """)

def _setup_period_structure(cr):
    """Création/Mise à jour de la structure des périodes"""
    if not table_exists(cr, 'calendar_period'):
        cr.execute("""
            CREATE TABLE calendar_period (
                id serial PRIMARY KEY,
                name varchar NOT NULL,
                start_date date NOT NULL,
                end_date date NOT NULL,
                region_id integer REFERENCES calendar_region(id) ON DELETE CASCADE,
                type varchar DEFAULT 'regular',
                active boolean DEFAULT true,
                create_uid integer REFERENCES res_users(id),
                create_date timestamp without time zone DEFAULT now(),
                write_uid integer REFERENCES res_users(id),
                write_date timestamp without time zone DEFAULT now(),
                CONSTRAINT date_check CHECK (end_date >= start_date)
            )
        """)

        # Index pour les performances
        cr.execute("""
            CREATE INDEX IF NOT EXISTS calendar_period_dates_idx 
            ON calendar_period (start_date, end_date);
            CREATE INDEX IF NOT EXISTS calendar_period_region_id_idx 
            ON calendar_period (region_id);
        """)

def _setup_access_rights(cr):
    """Configuration des droits d'accès"""
    access_rights = [
        ('access_calendar_region_user', 'calendar.region', 'base.group_user', 1, 0, 0, 0),
        ('access_calendar_region_manager', 'calendar.region', 'base.group_system', 1, 1, 1, 1),
        ('access_calendar_holiday_user', 'calendar.holiday', 'base.group_user', 1, 0, 0, 0),
        ('access_calendar_holiday_manager', 'calendar.region', 'base.group_system', 1, 1, 1, 1),
        ('access_calendar_period_user', 'calendar.period', 'base.group_user', 1, 0, 0, 0),
        ('access_calendar_period_manager', 'calendar.period', 'base.group_system', 1, 1, 1, 1)
    ]

    for access in access_rights:
        cr.execute("""
            INSERT INTO ir_model_access (
                name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink
            )
            SELECT 
                %s,
                (SELECT id FROM ir_model WHERE model = %s),
                (SELECT id FROM res_groups WHERE xml_id = %s),
                %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM ir_model_access WHERE name = %s
            )
        """, (access[0], access[1], access[2], access[3], access[4], access[5], access[6], access[0]))

    _logger.info("Migration WAF Tempo terminée avec succès") 