from . import controllers
from . import models

def pre_init_hook(env):
    """Pre-init hook to install French CoA."""
    # Installer d'abord le module l10n_fr s'il n'est pas déjà installé
    if not env['ir.module.module'].search([('name', '=', 'l10n_fr'), ('state', '=', 'installed')]):
        module = env['ir.module.module'].search([('name', '=', 'l10n_fr')])
        if module:
            module.button_immediate_install()
    
    # Maintenant on peut installer le plan comptable
    cr = env.cr
    cr.execute("SELECT id FROM res_company WHERE id = 1")
    company_id = cr.fetchone()[0]
    
    # Requête SQL pour obtenir l'ID du template
    cr.execute("""
        SELECT res_id 
        FROM ir_model_data 
        WHERE module = 'l10n_fr' 
        AND name = 'l10n_fr_pcg_chart_template'
    """)
    result = cr.fetchone()
    if result:
        template_id = result[0]
        # Installation du plan comptable via SQL
        from odoo.addons.account.models.chart_template import AccountChartTemplate
        AccountChartTemplate.try_loading(cr, template_id, company_id)
