"""
Script de migration ResCountryState v17.0.1.0
Gestion des régions et départements français
"""
import logging
from psycopg2 import sql
from odoo.tools import column_exists, table_exists
from contextlib import contextmanager

_logger = logging.getLogger(__name__)

# Données de référence complètes pour les régions et départements français
REGIONS_DATA = {
    'ARA': {
        'name': 'Auvergne-Rhône-Alpes',
        'departments': {
            '01': 'Ain', '03': 'Allier', '07': 'Ardèche', '15': 'Cantal',
            '26': 'Drôme', '38': 'Isère', '42': 'Loire', '43': 'Haute-Loire',
            '63': 'Puy-de-Dôme', '69': 'Rhône', '73': 'Savoie', '74': 'Haute-Savoie'
        }
    },
    'BFC': {
        'name': 'Bourgogne-Franche-Comté',
        'departments': {
            '21': 'Côte-d\'Or', '25': 'Doubs', '39': 'Jura', '58': 'Nièvre',
            '70': 'Haute-Saône', '71': 'Saône-et-Loire', '89': 'Yonne', '90': 'Territoire de Belfort'
        }
    },
    'BRE': {
        'name': 'Bretagne',
        'departments': {
            '22': 'Côtes-d\'Armor', '29': 'Finistère', '35': 'Ille-et-Vilaine', '56': 'Morbihan'
        }
    },
    'CVL': {
        'name': 'Centre-Val de Loire',
        'departments': {
            '18': 'Cher', '28': 'Eure-et-Loir', '36': 'Indre', '37': 'Indre-et-Loire',
            '41': 'Loir-et-Cher', '45': 'Loiret'
        }
    },
    'GES': {
        'name': 'Grand Est',
        'departments': {
            '08': 'Ardennes', '10': 'Aube', '51': 'Marne', '52': 'Haute-Marne',
            '54': 'Meurthe-et-Moselle', '55': 'Meuse', '57': 'Moselle',
            '67': 'Bas-Rhin', '68': 'Haut-Rhin', '88': 'Vosges'
        }
    },
    'HDF': {
        'name': 'Hauts-de-France',
        'departments': {
            '02': 'Aisne', '59': 'Nord', '60': 'Oise', '62': 'Pas-de-Calais', '80': 'Somme'
        }
    },
    'IDF': {
        'name': 'Île-de-France',
        'departments': {
            '75': 'Paris', '77': 'Seine-et-Marne', '78': 'Yvelines', '91': 'Essonne',
            '92': 'Hauts-de-Seine', '93': 'Seine-Saint-Denis', '94': 'Val-de-Marne', '95': 'Val-d\'Oise'
        }
    },
    'NOR': {
        'name': 'Normandie',
        'departments': {
            '14': 'Calvados', '27': 'Eure', '50': 'Manche', '61': 'Orne', '76': 'Seine-Maritime'
        }
    },
    'NAQ': {
        'name': 'Nouvelle-Aquitaine',
        'departments': {
            '16': 'Charente', '17': 'Charente-Maritime', '19': 'Corrèze', '23': 'Creuse',
            '24': 'Dordogne', '33': 'Gironde', '40': 'Landes', '47': 'Lot-et-Garonne',
            '64': 'Pyrénées-Atlantiques', '79': 'Deux-Sèvres', '86': 'Vienne', '87': 'Haute-Vienne'
        }
    },
    'OCC': {
        'name': 'Occitanie',
        'departments': {
            '09': 'Ariège', '11': 'Aude', '12': 'Aveyron', '30': 'Gard', '31': 'Haute-Garonne',
            '32': 'Gers', '34': 'Hérault', '46': 'Lot', '48': 'Lozère', '65': 'Hautes-Pyrénées',
            '66': 'Pyrénées-Orientales', '81': 'Tarn', '82': 'Tarn-et-Garonne'
        }
    },
    'PDL': {
        'name': 'Pays de la Loire',
        'departments': {
            '44': 'Loire-Atlantique', '49': 'Maine-et-Loire', '53': 'Mayenne',
            '72': 'Sarthe', '85': 'Vendée'
        }
    },
    'PAC': {
        'name': 'Provence-Alpes-Côte d\'Azur',
        'departments': {
            '04': 'Alpes-de-Haute-Provence', '05': 'Hautes-Alpes', '06': 'Alpes-Maritimes',
            '13': 'Bouches-du-Rhône', '83': 'Var', '84': 'Vaucluse'
        }
    },
    'COR': {
        'name': 'Corse',
        'departments': {
            '2A': 'Corse-du-Sud', '2B': 'Haute-Corse'
        }
    },
    'ROM': {
        'name': 'Régions d\'Outre-Mer',
        'departments': {
            '971': 'Guadeloupe', '972': 'Martinique', '973': 'Guyane',
            '974': 'La Réunion', '976': 'Mayotte'
        }
    }
}

@contextmanager
def savepoint(cr, name):
    """Gestionnaire de contexte pour les savepoints"""
    try:
        cr.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(name)))
        yield
    except Exception as e:
        cr.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(name)))
        raise e
    finally:
        cr.execute(sql.SQL("RELEASE SAVEPOINT {}").format(sql.Identifier(name)))

class StateMigration:
    def __init__(self, cr):
        self.cr = cr
        self.france_id = self._get_france_id()

    def _get_france_id(self):
        """Récupère l'ID de la France"""
        self.cr.execute("SELECT id FROM res_country WHERE code = 'FR'")
        result = self.cr.fetchone()
        if not result:
            raise ValueError("Pays 'France' non trouvé dans la base de données")
        return result[0]

    def validate_data(self):
        """Validation des données de référence"""
        for code, data in REGIONS_DATA.items():
            if not isinstance(code, str) or len(code) != 3:
                raise ValueError(f"Code région invalide: {code}")
            for dept_code in data['departments']:
                if not isinstance(dept_code, str) or not (2 <= len(dept_code) <= 3):
                    raise ValueError(f"Code département invalide: {dept_code}")

    def setup_structure(self):
        """Configuration de la structure de la table"""
        columns = {
            'is_region': 'boolean DEFAULT false',
            'is_department': 'boolean DEFAULT false',
            'parent_id': 'integer REFERENCES res_country_state(id)',
            'insee_code': 'varchar(3)',
            'active': 'boolean DEFAULT true'
        }
        
        with savepoint(self.cr, "structure"):
            for column, definition in columns.items():
                if not column_exists(self.cr, 'res_country_state', column):
                    self.cr.execute(sql.SQL("""
                        ALTER TABLE res_country_state 
                        ADD COLUMN {} {}
                    """).format(
                        sql.Identifier(column),
                        sql.SQL(definition)
                    ))

    def create_indexes(self):
        """Création des index optimisés"""
        indexes = [
            ('state_parent_id_idx', 'parent_id'),
            ('state_is_region_idx', 'is_region WHERE is_region'),
            ('state_is_department_idx', 'is_department WHERE is_department'),
            ('state_insee_code_idx', 'insee_code'),
            ('state_code_country_idx', '(code, country_id)')
        ]

        with savepoint(self.cr, "indexes"):
            for name, definition in indexes:
                self.cr.execute(sql.SQL("""
                    CREATE INDEX IF NOT EXISTS {} ON res_country_state ({})
                """).format(
                    sql.Identifier(name),
                    sql.SQL(definition)
                ))

    def cleanup_data(self):
        """Nettoyage des données incohérentes"""
        with savepoint(self.cr, "cleanup"):
            self.cr.execute("""
                UPDATE res_country_state
                SET parent_id = NULL
                WHERE parent_id IS NOT NULL 
                AND parent_id NOT IN (
                    SELECT id FROM res_country_state 
                    WHERE is_region IS TRUE
                )
            """)

    def migrate_regions(self):
        """Migration des régions"""
        with savepoint(self.cr, "regions"):
            for code, data in REGIONS_DATA.items():
                self.cr.execute("""
                    INSERT INTO res_country_state 
                        (name, code, country_id, is_region, active)
                    VALUES (%s, %s, %s, true, true)
                    ON CONFLICT (code, country_id) 
                    DO UPDATE SET 
                        name = EXCLUDED.name,
                        is_region = true
                    RETURNING id
                """, (data['name'], code, self.france_id))
                
                region_id = self.cr.fetchone()[0]
                self._migrate_departments(region_id, code, data['departments'])

    def _migrate_departments(self, region_id, region_code, departments):
        """Migration des départements d'une région"""
        for code, name in departments.items():
            self.cr.execute("""
                INSERT INTO res_country_state (
                    name, code, country_id, parent_id, 
                    is_department, insee_code, active
                )
                VALUES (%s, %s, %s, %s, true, %s, true)
                ON CONFLICT (code, country_id) 
                DO UPDATE SET 
                    name = EXCLUDED.name,
                    parent_id = EXCLUDED.parent_id,
                    is_department = true,
                    insee_code = EXCLUDED.insee_code
            """, (name, code, self.france_id, region_id, code))

    def setup_constraints(self):
        """Configuration des contraintes"""
        constraints = [
            ('unique_insee_code', 
             'UNIQUE(insee_code) WHERE insee_code IS NOT NULL',
             'Le code INSEE doit être unique'),
            ('check_parent_region', 
             'CHECK(parent_id IS NULL OR is_department)',
             'Seuls les départements peuvent avoir une région parente'),
            ('check_region_department',
             'CHECK(NOT (is_region AND is_department))',
             'Un état ne peut pas être à la fois une région et un département')
        ]

        with savepoint(self.cr, "constraints"):
            for name, definition, message in constraints:
                # Suppression sécurisée de la contrainte existante
                self.cr.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = %s
                        ) THEN
                            EXECUTE 'ALTER TABLE res_country_state DROP CONSTRAINT ' || %s;
                        END IF;
                    END $$;
                """, (name, name))

                # Création de la nouvelle contrainte
                self.cr.execute(sql.SQL("""
                    ALTER TABLE res_country_state 
                    ADD CONSTRAINT {} {}
                """).format(
                    sql.Identifier(name),
                    sql.SQL(definition)
                ))

    def log_statistics(self):
        """Journalisation des statistiques"""
        self.cr.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE is_region) as regions,
                COUNT(*) FILTER (WHERE is_department) as departments
            FROM res_country_state
            WHERE country_id = %s
        """, (self.france_id,))
        stats = self.cr.fetchone()
        _logger.info(
            "Migration terminée: %s régions, %s départements", 
            stats[0], stats[1]
        )

def migrate(cr, version):
    """Point d'entrée de la migration"""
    _logger.warning("=== DÉBUT MIGRATION REGIONS/DÉPARTEMENTS (version: %s) ===", version)
    
    try:
        migration = StateMigration(cr)
        
        with savepoint(cr, "main_migration"):
            migration.validate_data()
            migration.setup_structure()
            migration.create_indexes()
            migration.cleanup_data()
            migration.migrate_regions()
            migration.setup_constraints()
            
        migration.log_statistics()
        _logger.info("Migration terminée avec succès")
        
    except Exception as e:
        _logger.error("Erreur critique durant la migration: %s", str(e))
        raise
