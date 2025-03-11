from odoo import SUPERUSER_ID, api
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Migration des dispatches pour Odoo 17.
    
    Améliore la structure des données et ajoute le support de l'état 'shipped'.
    """
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Début de la migration des dispatches vers Odoo 17")
    
    # 0. Nettoyage des données liées aux groupes de dispatch
    _logger.info("Nettoyage des données liées aux groupes de dispatch")
    cr.execute("""
        -- Suppression des règles d'accès pour les groupes de dispatch
        DELETE FROM ir_model_access 
        WHERE model_id IN (
            SELECT id FROM ir_model 
            WHERE model = 'sale.line.dispatch.group'
        );

        -- Suppression des données des groupes de dispatch
        DROP TABLE IF EXISTS sale_line_dispatch_group CASCADE;
    """)
    
    # 1. Structure de la table
    cr.execute("""
        -- Ajout des nouveaux champs dans sale_line_dispatch
        ALTER TABLE sale_line_dispatch
        ADD COLUMN IF NOT EXISTS effective_date timestamp without time zone,
        ADD COLUMN IF NOT EXISTS amount_total numeric,
        ADD COLUMN IF NOT EXISTS dispatch_display_name varchar,
        ADD COLUMN IF NOT EXISTS currency_id integer,
        ADD COLUMN IF NOT EXISTS unit_price numeric,
        ADD COLUMN IF NOT EXISTS notes text;

        -- Ajout des contraintes de clé étrangère pour sale_line_dispatch
        DO $$
        BEGIN
            ALTER TABLE sale_line_dispatch
            ADD CONSTRAINT sale_line_dispatch_currency_id_fkey
            FOREIGN KEY (currency_id) REFERENCES res_currency(id);
        EXCEPTION WHEN others THEN NULL;
        END $$;
        
        -- Modification du champ state dans sale_line_dispatch
        DO $$
        BEGIN
            ALTER TABLE sale_line_dispatch
            DROP CONSTRAINT IF EXISTS sale_line_dispatch_state_check;
            
            ALTER TABLE sale_line_dispatch
            ADD CONSTRAINT sale_line_dispatch_state_check
            CHECK (state IN ('draft', 'confirmed', 'shipped', 'done', 'cancel'));
        EXCEPTION WHEN others THEN NULL;
        END $$;

        -- Ajout de la contrainte de quantité positive
        DO $$
        BEGIN
            ALTER TABLE sale_line_dispatch
            ADD CONSTRAINT positive_quantity
            CHECK (quantity > 0);
        EXCEPTION WHEN others THEN NULL;
        END $$;

        -- Ajout des champs d'adresse dans stock_picking
        ALTER TABLE stock_picking
        ADD COLUMN IF NOT EXISTS delivery_address_id integer,
        ADD COLUMN IF NOT EXISTS street varchar,
        ADD COLUMN IF NOT EXISTS street2 varchar,
        ADD COLUMN IF NOT EXISTS zip varchar,
        ADD COLUMN IF NOT EXISTS city varchar,
        ADD COLUMN IF NOT EXISTS state_id integer,
        ADD COLUMN IF NOT EXISTS country_id integer,
        ADD COLUMN IF NOT EXISTS dispatch_id integer;

        -- Ajout des contraintes de clé étrangère pour stock_picking
        DO $$
        BEGIN
            ALTER TABLE stock_picking
            ADD CONSTRAINT stock_picking_delivery_address_id_fkey
            FOREIGN KEY (delivery_address_id) REFERENCES partner_address(id);

            ALTER TABLE stock_picking
            ADD CONSTRAINT stock_picking_state_id_fkey
            FOREIGN KEY (state_id) REFERENCES res_country_state(id);

            ALTER TABLE stock_picking
            ADD CONSTRAINT stock_picking_country_id_fkey
            FOREIGN KEY (country_id) REFERENCES res_country(id);

            ALTER TABLE stock_picking
            ADD CONSTRAINT stock_picking_dispatch_id_fkey
            FOREIGN KEY (dispatch_id) REFERENCES sale_line_dispatch(id)
            ON DELETE SET NULL;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """)

    # 2. Mise à jour des données
    cr.execute("""
        -- Mise à jour des montants et prix unitaires
        UPDATE sale_line_dispatch d
        SET currency_id = so.currency_id,
            unit_price = sol.price_unit,
            amount_total = ROUND(d.quantity * sol.price_unit, 2)
        FROM sale_order so
        JOIN sale_order_line sol ON sol.order_id = so.id
        WHERE sol.id = d.sale_order_line_id;

        -- Mise à jour du display_name
        UPDATE sale_line_dispatch d
        SET dispatch_display_name = CONCAT(
            COALESCE(d.name, ''),
            ' - ',
            COALESCE((SELECT name FROM sale_order WHERE id = d.sale_order_id), ''),
            ' - ',
            COALESCE((SELECT name FROM product_product pp 
                      JOIN sale_order_line sol ON sol.product_id = pp.id 
                      WHERE sol.id = d.sale_order_line_id), '')
        )
        WHERE dispatch_display_name IS NULL;

        -- Liaison entre stock.picking et sale.line.dispatch
        UPDATE stock_picking sp
        SET dispatch_id = d.id,
            delivery_address_id = d.delivery_address_id,
            street = pa.street,
            street2 = pa.street2,
            zip = pa.zip,
            city = pa.city,
            state_id = pa.state_id,
            country_id = pa.country_id
        FROM sale_line_dispatch d
        JOIN partner_address pa ON pa.id = d.delivery_address_id
        WHERE sp.origin LIKE '%' || d.name || '%'
        AND sp.dispatch_id IS NULL;

        -- Migration des états et dates effectives
        UPDATE sale_line_dispatch d
        SET 
            state = CASE 
                WHEN sp.state = 'done' THEN 'shipped'
                WHEN sp.state = 'cancel' THEN 'cancel'
                ELSE d.state
            END,
            effective_date = sp.date_done
        FROM stock_picking sp
        WHERE sp.dispatch_id = d.id;
    """)

    # 3. Optimisation et indexes
    cr.execute("""
        -- Indexes pour sale_line_dispatch
        CREATE INDEX IF NOT EXISTS sale_line_dispatch_state_effective_date_idx 
        ON sale_line_dispatch(state, effective_date);
        
        CREATE INDEX IF NOT EXISTS sale_line_dispatch_display_name_idx 
        ON sale_line_dispatch(dispatch_display_name);
        
        CREATE INDEX IF NOT EXISTS sale_line_dispatch_amount_total_idx 
        ON sale_line_dispatch(amount_total);

        CREATE INDEX IF NOT EXISTS sale_line_dispatch_currency_id_idx
        ON sale_line_dispatch(currency_id);

        -- Indexes pour stock_picking
        CREATE INDEX IF NOT EXISTS stock_picking_dispatch_id_idx
        ON stock_picking(dispatch_id);

        CREATE INDEX IF NOT EXISTS stock_picking_delivery_address_id_idx
        ON stock_picking(delivery_address_id);

        CREATE INDEX IF NOT EXISTS stock_picking_address_idx
        ON stock_picking(zip, city, country_id);
        
        -- Mise à jour des statistiques
        ANALYZE sale_line_dispatch;
        ANALYZE stock_picking;
    """)

    _logger.info("Migration des dispatches terminée avec succès")
