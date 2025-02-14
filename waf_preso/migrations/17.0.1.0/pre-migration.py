"""
Script de migration WAF Preso v17.0.1.0
Auteur: [Votre nom]
Date: 13/02/2025
Version: 17.0.1.0
"""

import logging
from psycopg2 import sql
from odoo.tools import column_exists, table_exists
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class WafPresoMigration:
    def __init__(self, cr):
        self.cr = cr
        self.total_steps = 5
        self.current_step = 0

    def execute_step(self, step_function, description):
        """Exécute une étape de migration avec gestion des erreurs"""
        self.current_step += 1
        _logger.info(
            "Migration WAF Preso - Étape %s/%s : %s",
            self.current_step, self.total_steps, description
        )
        
        try:
            with self.cr.savepoint():
                step_function()
                self.cr.execute("ANALYZE")  # Optimisation des statistiques
        except Exception as e:
            _logger.error(
                "Erreur à l'étape %s (%s): %s",
                self.current_step, description, str(e)
            )
            raise UserError(f"Erreur de migration: {str(e)}")

    def migrate(self):
        """Fonction principale de migration"""
        _logger.info("Début migration WAF Preso v17.0.1.0")
        
        steps = [
            (self._pre_migrate_structure, "Structure de base"),
            (self._migrate_data, "Migration des données"),
            (self._post_migrate_checks, "Vérifications"),
            (self._finalize_migration, "Finalisation"),
            (self._configure_security, "Sécurité et menus")
        ]

        for step_func, description in steps:
            self.execute_step(step_func, description)

        self._log_migration_stats()
        _logger.info("Migration WAF Preso v17.0.1.0 terminée avec succès")

    def _pre_migrate_structure(self):
        """Préparation des structures"""
        # Création des tables principales
        self._create_main_tables()
        # Création des tables de relation
        self._create_relation_tables()
        # Création des index
        self._create_indexes()
        # Ajout des colonnes
        self._add_columns()

    def _migrate_data(self):
        """Migration des données"""
        queries = [
            # Migration des zones
            """
            INSERT INTO delivery_zone (name, code, company_id, state)
            SELECT DISTINCT 
                dp.name, 
                dp.code,
                dp.company_id,
                'active'
            FROM delivery_points dp
            WHERE NOT EXISTS (
                SELECT 1 FROM delivery_zone 
                WHERE code = dp.code
            )
            """,
            # Migration des créneaux
            """
            INSERT INTO delivery_time_slot (name, start_hour, end_hour)
            SELECT 
                name,
                EXTRACT(HOUR FROM start_time),
                EXTRACT(HOUR FROM end_time)
            FROM delivery_slots
            """
        ]
        
        for query in queries:
            self.cr.execute(query)

    def _post_migrate_checks(self):
        """Vérifications post-migration"""
        # Vérification de l'intégrité des données
        checks = [
            ("delivery_zone", "code IS NOT NULL"),
            ("delivery_time_slot", "start_hour < end_hour"),
            ("delivery_weekday", "code IN ('1','2','3','4','5','6','7')")
        ]

        for table, condition in checks:
            self.cr.execute(f"""
                SELECT COUNT(*) FROM {table}
                WHERE NOT ({condition})
            """)
            if self.cr.fetchone()[0] > 0:
                raise UserError(f"Données invalides détectées dans {table}")

    def _finalize_migration(self):
        """Finalisation de la migration"""
        # Mise à jour des séquences
        sequences = [
            ('delivery_zone_seq', 'delivery_zone'),
            ('delivery_slot_seq', 'delivery_time_slot')
        ]

        for seq_name, table in sequences:
            self.cr.execute(f"""
                SELECT setval('{seq_name}', 
                    (SELECT COALESCE(MAX(id) + 1, 1) FROM {table}), false)
            """)

    def _configure_security(self):
        """Configuration de la sécurité"""
        # Création des règles d'accès
        self._create_access_rules()
        # Configuration des menus
        self._configure_menus()

    def _log_migration_stats(self):
        """Log des statistiques de migration"""
        tables = ['delivery_zone', 'delivery_time_slot', 'delivery_weekday']
        
        for table in tables:
            self.cr.execute(f"SELECT COUNT(*) FROM {table}")
            count = self.cr.fetchone()[0]
            _logger.info(f"Total {table}: {count} enregistrements")

def migrate(cr, version):
    """Point d'entrée de la migration"""
    if not version:
        return
    
    migration = WafPresoMigration(cr)
    migration.migrate()