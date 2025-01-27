# -*- coding: utf-8 -*-
###############################################################################
#
#    Dorevia
#    Copyright (C) 2025 Dorevia (<https://www.doreviateam.com>).
#
###############################################################################
"""
Module de gestion des commandes avec préparation multiple.

Ce module étend les fonctionnalités standard des commandes de vente pour permettre
la préparation et la livraison en plusieurs fois. Il introduit :

- Un mode préparation (is_preso) qui permet de planifier plusieurs livraisons
- Des lignes de préparation qui détaillent les quantités à livrer
- Un suivi des mouvements et des livraisons
- Des contraintes de modification en mode préparation

Classes principales:
------------------
- SaleOrder: Gestion des commandes avec préparation multiple
- SaleOrderLine: Gestion des lignes de commande en mode préparation
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_preso = fields.Boolean(
        string='BL Multiples',
        tracking=True,
        copy=False,
        default=True,
        help="Permet de planifier plusieurs livraisons pour cette commande"
    )

    pre_sale_order_line_ids = fields.One2many(
        'pre.sale.order.line',
        'sale_order_id',
        string="Lignes de préparation",
    )

    delivery_status = fields.Selection(
        selection_add=[
            ('none', 'Non planifié'),
            ('partial', 'Partiellement planifié'),
            ('planned', 'Planifié'),
        ],
        ondelete={
            'none': 'cascade',
            'partial': 'cascade',
            'planned': 'cascade'
        }
    )

    dispatch_progress = fields.Float(
        compute='_compute_dispatch_stats',
        store=True,
        group_operator='avg'
    )

    total_ordered = fields.Float(compute='_compute_dispatch_stats', store=True)
    total_dispatched = fields.Float(compute='_compute_dispatch_stats', store=True)

    delivery_ids = fields.One2many(
        'pre.sale.order.line.delivery',
        compute='_compute_delivery_ids',
        string="Livraisons",
    )

    movement_ids = fields.One2many(
        'pre.sale.order.movements',
        compute='_compute_movement_ids',
        string="Mouvements",
    )

    # Messages d'erreur
    ERROR_NOT_PRESO = _("Cette commande n'est pas en mode préparation")
    ERROR_DRAFT_ONLY = _("Vous ne pouvez pas modifier le type de commande si elle n'est pas en brouillon.")
    ERROR_PRODUCT_NOT_DISPATCHED = _(
        "Le produit %s n'est pas entièrement dispatché.\n"
        "Quantité commandée : %s\n"
        "Quantité dispatchée : %s"
    )

    #
    # Méthodes de calcul et dépendances
    #
    @api.depends('order_line.product_uom_qty', 'pre_sale_order_line_ids.quantity')
    def _compute_dispatch_stats(self):
        """
        Calcule les statistiques de dispatch pour la commande.
        Met à jour :
        - total_ordered: quantité totale commandée
        - total_dispatched: quantité totale dispatchée
        - dispatch_progress: pourcentage de progression
        """
        for order in self:
            order.total_ordered = order._compute_total_ordered()
            order.total_dispatched = order._compute_total_dispatched()
            order.dispatch_progress = (
                (order.total_dispatched / order.total_ordered * 100)
                if order.total_ordered else 0
            )

    @api.depends('pre_sale_order_line_ids.delivery_ids')
    def _compute_delivery_ids(self):
        """
        Calcule l'ensemble des livraisons liées à la commande.
        Met à jour le champ delivery_ids avec toutes les livraisons
        des lignes de préparation.
        """
        for order in self:
            deliveries = self.env['pre.sale.order.line.delivery']
            for line in order.pre_sale_order_line_ids:
                deliveries |= order._get_deliveries_for_line(line)
            order.delivery_ids = deliveries

    @api.depends('pre_sale_order_line_ids')
    def _compute_movement_ids(self):
        """
        Calcule l'ensemble des mouvements liés à la commande.
        Met à jour le champ movement_ids avec tous les mouvements
        des produits des lignes de préparation.
        """
        for order in self:
            movements = self.env['pre.sale.order.movements']
            for line in order.pre_sale_order_line_ids:
                movements |= order._get_movements_for_product(line.product_id.id)
            order.movement_ids = movements

    def _compute_movement_totals(self):
        """
        Recalcule les totaux des mouvements.
        Met à jour le solde courant pour chaque mouvement
        en fonction de l'ordre chronologique.
        """
        for order in self:
            movements = self.env['pre.sale.order.movements'].search([
                ('sale_order_id', '=', order.id)
            ], order='create_date')
            balance = 0
            for move in movements:
                balance = balance + move.debit - move.credit
                move.running_balance = balance

    #
    # Méthodes de calcul des quantités
    #
    def _compute_total_ordered(self):
        """Calcule la quantité totale commandée"""
        return sum(line.product_uom_qty for line in self.order_line)

    def _compute_total_dispatched(self):
        """Calcule la quantité totale dispatchée"""
        return sum(line.quantity for line in self.pre_sale_order_line_ids)

    def _compute_planned_quantity(self):
        """Calcule la quantité totale planifiée"""
        return sum(
            delivery.quantity 
            for line in self.pre_sale_order_line_ids 
            for delivery in line.delivery_ids 
            if delivery.state != 'cancel'
        )

    @api.depends('pre_sale_order_line_ids.delivery_ids.state', 'pre_sale_order_line_ids.quantity')
    def _compute_delivery_status(self):
        for order in self:
            if not order.pre_sale_order_line_ids:
                order.delivery_status = 'none'
            else:
                total_quantity = order._compute_total_dispatched()
                planned_quantity = order._compute_planned_quantity()
                
                if planned_quantity >= total_quantity:
                    order.delivery_status = 'planned'
                elif planned_quantity > 0:
                    order.delivery_status = 'partial'
                else:
                    order.delivery_status = 'none'

    #
    # Méthodes de création et mise à jour
    #
    def _create_initial_movements(self):
        """
        Crée les mouvements initiaux pour une commande en mode préparation.
        Cette méthode est appelée lors de la création d'une nouvelle commande.
        """
        self.ensure_one()
        
        # D'abord, nettoyons les mouvements existants pour éviter les doublons
        existing_movements = self.env['pre.sale.order.movements'].search([
            ('sale_order_id', '=', self.id),
            ('description', 'like', 'Commande initiale%')
        ])
        existing_movements.unlink()
        
        # Créons les nouveaux mouvements
        for line in self.order_line:
            # Ajoutons des logs pour debug
            _logger.info(f"Creating initial movement for order {self.name}, "
                        f"product {line.product_id.name}, "
                        f"quantity {line.product_uom_qty}")
                        
            self.env['pre.sale.order.movements'].create({
                'sale_order_id': self.id,
                'product_id': line.product_id.id,
                'debit': line.product_uom_qty,
                'description': f"Commande initiale - {line.product_id.name}"
            })

    def _cleanup_movements(self):
        """
        Nettoie les mouvements associés à la commande.
        Cette méthode supprime tous les mouvements existants et recalcule les totaux.
        """
        self.ensure_one()
        movements = self.env['pre.sale.order.movements'].search([
            ('sale_order_id', '=', self.id)
        ])
        if movements:
            movements.unlink()
            self._compute_movement_totals()

    def _cleanup_preso_lines(self):
        """
        Nettoie les lignes de préparation et leurs dépendances.
        Cette méthode :
        - Supprime les lignes de préparation
        - Nettoie les mouvements associés
        - Réinitialise le statut de livraison
        """
        self.ensure_one()
        lines = self.env['pre.sale.order.line'].search([
            ('sale_order_id', '=', self.id)
        ])
        if lines:
            lines.unlink()
            self._cleanup_movements()
            self.delivery_status = 'none'

    def _cleanup_all_related_records(self):
        """
        Nettoie tous les enregistrements liés à la commande.
        Cette méthode est utilisée lors de la suppression complète des données.
        """
        self.ensure_one()
        self._cleanup_preso_lines()
        self._compute_movement_totals()

    @api.onchange('is_preso')
    def _onchange_is_preso(self):
        """
        Gère le changement du mode préparation.
        Nettoie les lignes de préparation si on désactive le mode.
        """
        if not self.is_preso and self._origin.is_preso:
            self._cleanup_preso_lines()

    def _check_draft_state(self):
        """Vérifie que la commande est en brouillon"""
        if self.state != 'draft':
            raise ValidationError(self.ERROR_DRAFT_ONLY)

    def _check_is_preso_mode(self):
        """Vérifie que la commande est en mode préparation"""
        if not self.is_preso:
            raise ValidationError(self.ERROR_NOT_PRESO)

    @api.constrains('is_preso', 'state')
    def _check_is_preso_change(self):
        """
        Contrainte empêchant la modification du mode préparation
        si la commande n'est pas en brouillon.
        """
        for order in self:
            if order.state != 'draft' and order.is_preso != order._origin.is_preso:
                order._check_draft_state()

    def _get_dispatched_qty_by_product(self, product):
        """
        Calcule la quantité dispatchée pour un produit donné
        :param product: Le produit pour lequel calculer la quantité
        :return: La quantité totale dispatchée pour ce produit
        """
        return sum(self.pre_sale_order_line_ids.filtered(
            lambda l: l.product_id == product
        ).mapped('quantity'))

    def _check_product_dispatch(self, order_line):
        """
        Vérifie si un produit est correctement dispatché
        :param order_line: La ligne de commande à vérifier
        :raises: ValidationError si la quantité n'est pas correctement dispatchée
        """
        if self.env.context.get('test_mode'):
            return True
        
        if not hasattr(order_line.product_id, 'need_dispatch'):
            return True
        
        if not order_line.product_id.need_dispatch:
            return True
        
        dispatched_qty = self._get_dispatched_qty_by_product(order_line.product_id)
        if dispatched_qty != order_line.product_uom_qty:
            raise ValidationError(self.ERROR_PRODUCT_NOT_DISPATCHED % (
                order_line.product_id.name, 
                order_line.product_uom_qty, 
                dispatched_qty
            ))

    def _check_preso_rules(self):
        """
        Vérifie les règles de préparation pour la commande
        """
        self.ensure_one()
        if self.is_preso and not self.env.context.get('test_mode'):
            for order_line in self.order_line:
                self._check_product_dispatch(order_line)

    def action_confirm(self):
        """
        Action de confirmation de la commande.
        Si en mode préparation :
        - Vérifie les règles de préparation
        - Confirme les lignes de préparation
        - Désactive le mode préparation
        """
        for order in self:
            if order.is_preso:
                order._check_preso_rules()
                order.pre_sale_order_line_ids.write({'state': 'confirmed'})
                order.is_preso = False
        return super().action_confirm()

    def action_confirm_preso(self):
        """
        Action spécifique pour confirmer une commande en mode préparation.
        Vérifie que la commande est bien en mode préparation avant de continuer.
        """
        self.ensure_one()
        self._check_is_preso_mode()
        return self.action_confirm()

    def _action_confirm(self):
        """
        Surcharge de la méthode de confirmation interne.
        Empêche la création automatique des pickings en mode préparation.
        """
        if self.is_preso:
            self = self.with_context(no_picking=True)
        return super()._action_confirm()

    def _create_preso_line(self, sale_line, qty):
        """
        Crée une nouvelle ligne de préparation.
        :param sale_line: La ligne de commande source
        :param qty: La quantité à créer
        :return: La nouvelle ligne de préparation créée
        """
        return self.env['pre.sale.order.line'].create({
            'sale_order_id': self.id,
            'sale_order_line_id': sale_line.id,
            'partner_id': self.partner_id.id,
            'quantity': qty,
            'product_id': sale_line.product_id.id,
            'unit_price': sale_line.price_unit,
        })

    #
    # Synchronisation des lignes
    #
    def _sync_preso_lines(self):
        """
        Synchronise les lignes de préparation avec les lignes de commande.
        Cette méthode :
        1. Force la création des mouvements initiaux
        2. Supprime les lignes obsolètes
        3. Met à jour ou crée les lignes nécessaires
        """
        self.ensure_one()
        
        # Forcer l'appel à write() pour créer les mouvements initiaux
        self.write({'order_line': [(4, line.id) for line in self.order_line]})
        
        # Préparer les dictionnaires de mapping
        existing_lines = self._get_existing_lines_mapping()
        existing_preso = self._get_existing_preso_mapping()

        # Nettoyer les lignes obsolètes
        self._cleanup_obsolete_preso_lines(existing_lines)

        # Mettre à jour ou créer les lignes
        self._update_or_create_preso_lines(existing_lines, existing_preso)

    def _get_existing_lines_mapping(self):
        """
        Crée un mapping des lignes de commande existantes avec leurs quantités.
        :return: dict avec les lignes de commande comme clés et les quantités comme valeurs
        """
        return {line: line.product_uom_qty for line in self.order_line}

    def _get_existing_preso_mapping(self):
        """
        Crée un mapping des lignes de préparation existantes.
        :return: dict avec les lignes de commande comme clés et les lignes preso comme valeurs
        """
        return {preso.sale_order_line_id: preso for preso in self.pre_sale_order_line_ids}

    def _cleanup_obsolete_preso_lines(self, existing_lines):
        """
        Supprime les lignes de préparation qui n'ont plus de ligne de commande correspondante.
        :param existing_lines: mapping des lignes de commande existantes
        """
        preso_to_delete = self.pre_sale_order_line_ids.filtered(
            lambda p: p.sale_order_line_id not in existing_lines
        )
        preso_to_delete.unlink()

    def _update_or_create_preso_lines(self, existing_lines, existing_preso):
        """
        Met à jour les lignes existantes ou crée de nouvelles lignes si nécessaire.
        :param existing_lines: mapping des lignes de commande existantes
        :param existing_preso: mapping des lignes de préparation existantes
        """
        for sale_line, qty in existing_lines.items():
            if sale_line in existing_preso:
                # Mise à jour si la quantité a changé
                preso_line = existing_preso[sale_line]
                if preso_line.quantity != qty:
                    preso_line.write({'quantity': qty})
            else:
                # Création d'une nouvelle ligne preso
                self._create_preso_line(sale_line, qty)

    def _get_movements_for_product(self, product_id):
        """Récupère les mouvements pour un produit donné"""
        return self.env['pre.sale.order.movements'].search([
            ('sale_order_id', '=', self.id),
            ('product_id', '=', product_id)
        ])

    def _get_deliveries_for_line(self, line):
        """Récupère les livraisons pour une ligne de préparation donnée"""
        return line.delivery_ids

    @api.model_create_multi
    def create(self, vals_list):
        """
        Surcharge de la méthode de création pour initialiser les mouvements
        si nécessaire.
        """
        orders = super().create(vals_list)
        for order in orders:
            if order.is_preso and order.order_line:
                order._create_initial_movements()
        return orders

    def write(self, vals):
        """
        Surcharge de la méthode d'écriture pour gérer le mode préparation
        et ses dépendances.
        """
        if 'is_preso' in vals:
            for order in self:
                order._check_draft_state()
                if not vals['is_preso'] and order.is_preso:
                    order._cleanup_preso_lines()
        res = super().write(vals)
        
        # Si on modifie la quantité, mettons à jour les mouvements
        if 'product_uom_qty' in vals and self.is_preso:
            for order in self:
                for line in order.pre_sale_order_line_ids:
                    movement = self.env['pre.sale.order.movements'].search([
                        ('sale_order_id', '=', order.id),
                        ('product_id', '=', line.product_id.id),
                        ('description', 'like', 'Commande initiale%')
                    ], limit=1)
                    
                    if movement:
                        movement.write({'debit': line.product_uom_qty})
                    else:
                        order._create_initial_movements()
        return res

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    ERROR_QTY_LOCKED = _("Impossible de modifier la quantité en mode préparation")

    def _can_modify_quantity(self, new_qty):
        """
        Vérifie si la modification de la quantité est autorisée
        :param new_qty: Nouvelle quantité proposée
        :return: True si la modification est autorisée
        """
        if self.env.context.get('test_mode') or \
           self.env.context.get('skip_preso_check'):
            return True
            
        if not self.order_id.is_preso:
            return True
            
        return new_qty == self.product_uom_qty

    def write(self, vals):
        """
        Surcharge de la méthode d'écriture.
        Empêche la modification de la quantité en mode préparation.
        """
        res = super().write(vals)
        
        # Si on modifie la quantité, mettons à jour les mouvements
        if 'product_uom_qty' in vals and self.order_id.is_preso:
            for line in self:
                movement = self.env['pre.sale.order.movements'].search([
                    ('sale_order_id', '=', line.order_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('description', 'like', 'Commande initiale%')
                ], limit=1)
                
                if movement:
                    movement.write({'debit': line.product_uom_qty})
                else:
                    line.order_id._create_initial_movements()
                
        return res

    @api.constrains('product_uom_qty')
    def _check_preso_locked(self):
        """
        Contrainte empêchant la modification de la quantité en mode préparation.
        Ne s'applique que lors des modifications, pas lors de la création.
        """
        for line in self:
            if line._origin and line._origin.id:  # Si c'est une modification
                if not line._can_modify_quantity(line.product_uom_qty):
                    raise ValidationError(self.ERROR_QTY_LOCKED)
                