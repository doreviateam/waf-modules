from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from itertools import groupby
import logging
from datetime import datetime, time, date
import pytz

_logger = logging.getLogger(__name__)

class DispatchGroupment(models.Model):
    _inherit = 'sale.dispatch'

    def action_create_delivery(self):
        """Crée les BL groupés par date/stakeholder/adresse avec gestion optimisée des dates"""
        self.ensure_one()

        # 1. Récupération des lignes confirmées
        lines = self.line_ids.filtered(lambda l: l.state == 'confirmed')
        if not lines:
            raise UserError(_("Aucune ligne confirmée à livrer."))

        # 2. Groupage par date/stakeholder/adresse
        def groupby_key(line):
            return (
                line.scheduled_date,  # Déjà un objet Date
                line.stakeholder_id.id,
                line.delivery_address_id.id
            )

        sorted_lines = lines.sorted(key=groupby_key)
        grouped = groupby(sorted_lines, key=groupby_key)

        # 3. Création des BL
        pickings = self.env['stock.picking']
        for key, group_lines in grouped:
            group_lines = list(group_lines)
            self._validate_group_consistency(group_lines)
            
            picking_type = self.env.ref('stock.picking_type_out')
            location_id = picking_type.default_location_src_id
            location_dest_id = self.env.ref('stock.stock_location_customers')

            # Création du picking avec la date exacte du dispatch
            scheduled_date = key[0]  # La date du dispatch (Date)
            user_tz = self.env.user.tz or 'UTC'
            scheduled_dt = fields.Datetime.context_timestamp(
                self,
                fields.Datetime.from_string(f"{scheduled_date} 08:00:00")
            ).astimezone(pytz.UTC).replace(tzinfo=None)
            
            _logger.info(f"Création BL pour la date: {scheduled_dt} (depuis {scheduled_date})")

            picking = self.env['stock.picking'].create({
                'partner_id': group_lines[0].stakeholder_id.id,
                'delivery_address_id': group_lines[0].delivery_address_id.id,
                'scheduled_date': scheduled_dt,
                'picking_type_id': picking_type.id,
                'location_id': location_id.id,
                'location_dest_id': location_dest_id.id,
                'move_ids': [(0, 0, self._prepare_move(line)) for line in group_lines],
                'origin': f"{self.name} - {group_lines[0].order_id.name}",
                'company_id': self.env.company.id,
                'mandator_id': self.mandator_id.id,
                'priority': '1' if any(l.product_id.urgent_delivery for l in group_lines) else '0',
                'delivery_note': self._generate_delivery_notes(group_lines)
            })
            
            pickings += picking
            
            # Mise à jour des lignes
            for line in group_lines:
                line.write({
                    'picking_id': picking.id,
                    'state': 'done'
                })
            
            _logger.info(
                "BL %s créé pour %s le %s avec %d lignes", 
                picking.name, 
                picking.partner_id.name, 
                picking.scheduled_date,
                len(group_lines)
            )

        # 4. Lien avec le dispatch
        self.write({'picking_ids': [(4, p.id) for p in pickings]})
        return self.action_open_deliveries()

    def _prepare_move(self, line):
        """Prépare le mouvement de stock avec gestion des spécificités agro-alimentaires"""
        # S'assurer que nous avons une date (pas un datetime)
        scheduled_date = line.scheduled_date
        if isinstance(scheduled_date, datetime):
            scheduled_date = scheduled_date.date()
        elif isinstance(scheduled_date, str):
            scheduled_date = fields.Date.from_string(scheduled_date)

        # Conversion en datetime avec heure fixe
        deadline_dt = datetime.combine(scheduled_date, time(hour=8))
        
        _logger.info(f"Date limite pour le mouvement: {deadline_dt}")

        move_vals = {
            'product_id': line.product_id.id,
            'product_uom_qty': line.product_uom_qty,
            'product_uom': line.product_uom.id,
            'name': line.product_id.name,
            'date_deadline': deadline_dt,
            'sale_line_id': line.sale_order_line_id.id,
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        }

        # Gestion de la chaîne du froid
        if line.product_id.cold_chain_required:
            move_vals.update({
                'temperature_control': True,
                'max_temperature': 4,
                'tracking': 'lot'
            })

        return move_vals

    def _validate_group_consistency(self, lines):
        """Valide la cohérence du groupe de lignes"""
        if len({l.delivery_address_id for l in lines}) > 1:
            raise ValidationError(_("Adresses de livraison différentes dans le même groupe!"))

    def _generate_delivery_notes(self, lines):
        """Génère des notes de livraison spécifiques pour l'agro-alimentaire"""
        notes = []
        for line in lines:
            if line.product_id.perishable:
                notes.append(f"[FRAIS] {line.product_id.name} - À livrer avant {line.scheduled_date}")
            if line.product_id.allergens:
                notes.append(f"[ALLERGÈNES] {line.product_id.name}: {line.product_id.allergens}")
        return '\n'.join(notes)

    def action_open_deliveries(self):
        """Ouvre la vue des BL générés"""
        self.ensure_one()
        return {
            'name': _('Bons de livraison'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'context': {
                'default_dispatch_id': self.id,
                'group_by': 'scheduled_date'
            }
        }

    def action_done(self):
        """Valide le dispatch et les BL associés"""
        for dispatch in self:
            if not dispatch.picking_ids:
                dispatch.action_create_delivery()

            try:
                dispatch.picking_ids.write({'state': 'done'})
                dispatch.write({
                    'state': 'done',
                    'done_date': fields.Datetime.now()
                })
                self._log_delivery_performance()
            except Exception as e:
                _logger.error("Erreur validation BL : %s", str(e))
                raise UserError(_("Erreur lors de la validation : %s") % str(e))

    def _log_delivery_performance(self):
        """Journalise les performances de livraison"""
        delivery_time = sum(
            (p.scheduled_date - p.create_date).total_seconds() 
            for p in self.picking_ids
        ) / len(self.picking_ids)

        _logger.info(
            "[PERF] Livraison %s - Temps moyen: %.2f heures - Produits frais: %d",
            self.name,
            delivery_time / 3600,
            sum(1 for p in self.picking_ids.move_ids if p.product_id.perishable)
        )

    def _create_picking_with_fixed_time(self, lines, scheduled_date, hour=8):
        """Crée un BL avec une heure fixe pour la date planifiée"""
        # Conversion de la date en datetime avec heure fixe
        scheduled_dt = datetime.combine(
            scheduled_date, 
            time(hour=hour)
        )
        
        _logger.info(f"Création BL pour la date: {scheduled_dt}")

        # Création du picking
        picking = self.env['stock.picking'].create({
            'partner_id': lines[0].stakeholder_id.id,
            'delivery_address_id': lines[0].delivery_address_id.id,
            'scheduled_date': scheduled_dt,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'origin': f"{self.name} - {lines[0].order_id.name}",
            'company_id': self.env.company.id,
            'mandator_id': self.mandator_id.id,
            'move_type': 'direct',  # Pour s'assurer que la date est prise en compte
        })

        # Création des mouvements avec la même date
        for line in lines:
            move_vals = {
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom.id,
                'name': line.product_id.name,
                'date': scheduled_dt,  # Date du mouvement
                'date_deadline': scheduled_dt,  # Date limite
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'sale_line_id': line.sale_order_line_id.id,
            }
            self.env['stock.move'].create(move_vals)

        # Force la mise à jour de la date planifiée
        picking.write({
            'scheduled_date': scheduled_dt,
            'date': scheduled_dt,
        })

        return picking

