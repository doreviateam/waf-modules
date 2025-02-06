def migrate(cr, version):
    if not version:
        return

    # 1. Création de la table de relation many2many si elle n'existe pas
    cr.execute("""
        CREATE TABLE IF NOT EXISTS partner_agent_rel (
            partner_id integer NOT NULL,
            agent_id integer NOT NULL,
            CONSTRAINT partner_agent_rel_pkey PRIMARY KEY (partner_id, agent_id),
            CONSTRAINT partner_agent_rel_partner_id_fkey FOREIGN KEY (partner_id)
                REFERENCES res_partner (id) ON DELETE CASCADE,
            CONSTRAINT partner_agent_rel_agent_id_fkey FOREIGN KEY (agent_id)
                REFERENCES res_partner (id) ON DELETE CASCADE
        )
    """)

    # 2. Ajout de la colonne is_agent si elle n'existe pas
    cr.execute("""
        ALTER TABLE res_partner 
        ADD COLUMN IF NOT EXISTS is_agent boolean DEFAULT false
    """)

    # 3. Migration des données existantes
    cr.execute("""
        -- Marquer les agents existants
        UPDATE res_partner 
        SET is_agent = true 
        WHERE id IN (
            SELECT DISTINCT agent_id 
            FROM sale_order 
            WHERE agent_id IS NOT NULL
        );

        -- Créer les relations agent-partenaire depuis les commandes existantes
        INSERT INTO partner_agent_rel (partner_id, agent_id)
        SELECT DISTINCT dp.partner_id, so.agent_id
        FROM sale_order so
        JOIN sale_order_delivery_partner_rel dp ON dp.sale_order_id = so.id
        WHERE so.agent_id IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)

    # 4. Log pour vérification
    cr.execute("""
        SELECT COUNT(*) FROM partner_agent_rel
    """)
    count = cr.fetchone()[0]
    print(f"Migration terminée : {count} relations agent-partenaire créées")