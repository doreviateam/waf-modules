from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round
from odoo.tools.misc import clean_context


class LineOrder(models.Model):
    """Extension du modèle sale.order.line pour ajouter la fonctionnalité de dispatch.
    
    Ajoute la possibilité de créer plusieurs dispatches pour une même ligne de commande,
    permettant ainsi de répartir les quantités entre différentes parties prenantes.
    """
    _inherit = 'sale.order.line'

    dispatch_ids = fields.One2many(
        'sale.line.dispatch',
        'sale_line_id',
        string='Dispatches',
        help="Liste des dispatches créés pour cette ligne de commande"
    )

    remaining_after_dispatch = fields.Float(
        string='Quantité restante après dispatch',
        compute='_compute_remaining_after_dispatch',
        store=True,
        digits='Product Unit of Measure',
        help="Quantité restante à dispatcher sur cette ligne"
    )

    @api.depends('product_uom_qty', 'dispatch_ids.quantity', 'dispatch_ids.state')
    def _compute_remaining_after_dispatch(self):
        """Calcule la quantité restante à dispatcher sur la ligne de commande.
        
        Prend en compte tous les dispatches non annulés pour calculer
        la quantité encore disponible pour de nouveaux dispatches.
        """
        for line in self:
            dispatched_qty = sum(
                line.dispatch_ids.filtered(
                    lambda d: d.state not in ['cancel']
                ).mapped('quantity')
            )
            line.remaining_after_dispatch = line.product_uom_qty - dispatched_qty


class SaleLineDispatch(models.Model):
    """Modèle permettant la répartition des lignes de commande de vente.
    
    Ce modèle permet de dispatcher une ligne de commande vers différentes parties prenantes
    en gérant les quantités, les adresses de livraison et le suivi des états.
    
    Attributes:
        _name (str): Nom technique du modèle
        _description (str): Description humaine du modèle
        _inherit (list): Modèles hérités pour la traçabilité et les activités
        _order (str): Ordre de tri par défaut
    """
    _name = 'sale.line.dispatch'
    _description = 'Ligne de commande de vente à dispatcher'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    # Champs techniques
    active = fields.Boolean(
        string='Actif',
        default=True,
        tracking=True,
        help="Permet d'archiver/désarchiver le dispatch"
    )
    
    company_id = fields.Many2one(
        'res.company', 
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Société responsable du dispatch"
    )

    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        store=True,
        readonly=True,
        help="Devise de la commande, utilisée pour les calculs monétaires"
    )

    # Champs relationnels
    sale_order_id = fields.Many2one(
        'sale.order', 
        string='Commande de vente',
        required=True,
        tracking=True,
        index='btree',
        help="Commande de vente source du dispatch"
    )

    sale_line_id = fields.Many2one(
        'sale.order.line', 
        string='Ligne de commande',
        required=True,
        tracking=True,
        index='btree',
        domain="[('order_id', '=', sale_order_id)]",
        default=lambda self: self._context.get('default_sale_line_id', False),
        help="Ligne de commande à dispatcher"
    )

    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        related='sale_line_id.product_id',
        store=True,
        readonly=True,
        index='btree',
        help="Produit concerné par le dispatch"
    )

    # Champs quantité et montants
    quantity = fields.Float(
        string='Quantité',
        default=1.0,
        tracking=True,
        digits='Product Unit of Measure',
        group_operator='sum',
        help="Quantité à dispatcher pour cette partie prenante"
    )

    unit_price = fields.Float(
        string='Prix unitaire',
        related='sale_line_id.price_unit',
        readonly=True,
        store=True,
        digits='Product Price',
        help="Prix unitaire du produit, hérité de la ligne de commande"
    )

    amount_total = fields.Monetary(
        string='Montant total',
        compute='_compute_amount_total',
        store=True,
        help="Montant total du dispatch (quantité × prix unitaire)"
    )

    remaining_quantity = fields.Float(
        string='Quantité restante',
        related='sale_line_id.remaining_after_dispatch',
        store=True,
        digits='Product Unit of Measure',
        help="Quantité encore disponible pour dispatch sur la ligne"
    )

    # Champs partenaires
    stakeholder_id = fields.Many2one(
        'res.partner',
        string='Partie prenante',
        domain="[('is_company', '=', True)]",
        required=True,
        tracking=True,
        index='btree',
        help="Entreprise destinataire du dispatch"
    )

    delivery_address_id = fields.Many2one(
        'res.partner',
        string='Adresse de livraison',
        domain="[('type', '=', 'delivery'), ('parent_id', '=', stakeholder_id)]",
        required=True,
        tracking=True,
        index='btree',
        help="Adresse de livraison pour ce dispatch"
    )

    # Champs de statut et suivi
    state = fields.Selection(
        string='État',
        selection=[
            ('draft', 'Brouillon'),
            ('confirmed', 'Confirmé'),
            ('done', 'Terminé'),
            ('cancel', 'Annulé')
        ],
        default='draft',
        tracking=True,
        index=True,
        copy=False,
        help="État du dispatch dans son cycle de vie"
    )

    notes = fields.Text(
        string='Notes',
        tracking=True,
        help="Notes internes concernant ce dispatch"
    )

    display_name = fields.Char(
        string='Nom affiché',
        compute='_compute_display_name',
        store=True,
        help="Nom complet du dispatch pour affichage"
    )

    # Contraintes SQL
    _sql_constraints = [
        ('positive_quantity', 
         'CHECK(quantity > 0)', 
         'La quantité doit être positive')
    ]

    @api.model
    def _get_sale_order_domain(self):
        """Définit le domaine de filtrage des commandes disponibles pour dispatch.
        
        Returns:
            list: Domaine limitant aux commandes confirmées ou terminées
        """
        return [('state', 'in', ['sale', 'done'])]

    @api.depends('quantity', 'unit_price')
    def _compute_amount_total(self):
        """Calcule le montant total du dispatch.
        
        Multiplie la quantité par le prix unitaire en respectant la précision
        de la devise de la commande.
        """
        for record in self:
            if record.currency_id and record.currency_id.rounding:
                record.amount_total = float_round(
                    record.quantity * record.unit_price,
                    precision_rounding=record.currency_id.rounding
                )
            else:
                # Fallback sur la précision standard des prix produits
                record.amount_total = float_round(
                    record.quantity * record.unit_price,
                    precision_digits=2
                )

    @api.depends('sale_line_id.remaining_after_dispatch', 'quantity', 'state')
    def _compute_remaining_quantity(self):
        """Calcule la quantité restante disponible pour le dispatch.
        
        Prend en compte l'état du dispatch actuel pour ajuster le calcul:
        - En brouillon: ajoute sa propre quantité car déjà déduite
        - Autres états: utilise directement la quantité restante
        """
        for record in self:
            if record.sale_line_id:
                adjustment = record.quantity if record.state == 'draft' else 0
                record.remaining_quantity = record.sale_line_id.remaining_after_dispatch + adjustment
            else:
                record.remaining_quantity = 0.0

    @api.depends('sale_order_id.name', 'product_id.name', 'stakeholder_id.name')
    def _compute_display_name(self):
        """Génère un nom d'affichage unique et descriptif.
        
        Format: "Commande/Produit - Partie prenante"
        """
        for record in self:
            if not record.sale_order_id or not record.product_id or not record.stakeholder_id:
                record.display_name = "..."
            else:
                record.display_name = f"{record.sale_order_id.name}/{record.product_id.name} - {record.stakeholder_id.name}"

    @api.constrains('quantity', 'sale_line_id')
    def _check_quantity(self):
        """Valide que la quantité dispatché ne dépasse pas la quantité disponible.
        
        Raises:
            ValidationError: Si la quantité dépasse le disponible
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for record in self:
            if not record.sale_line_id:
                continue
            available = record.sale_line_id.remaining_after_dispatch
            if record.state == 'draft':
                available += record.quantity
            if float_compare(record.quantity, available, precision_digits=precision) > 0:
                raise ValidationError(_(
                    "La quantité ne peut pas dépasser la quantité restante (%(remaining)s)",
                    remaining=available
                ))

    def action_confirm(self):
        """Confirme les dispatches en état brouillon.
        
        Returns:
            bool: True en cas de succès
        """
        self.filtered(lambda r: r.state == 'draft').write({'state': 'confirmed'})
        return True

    def action_done(self):
        """Marque les dispatches confirmés comme terminés.
        
        Returns:
            bool: True en cas de succès
        """
        for record in self.filtered(lambda r: r.state == 'confirmed'):
            record.write({'state': 'done'})
        return True

    def action_draft(self):
        """Repasse les dispatches en état brouillon.
        
        Applicable uniquement aux dispatches confirmés ou annulés.
        
        Returns:
            bool: True en cas de succès
        """
        self.filtered(lambda r: r.state in ['confirmed', 'cancel']).write({'state': 'draft'})
        return True

    def action_cancel(self):
        """Annule les dispatches non terminés.
        
        Returns:
            bool: True en cas de succès
        """
        self.filtered(lambda r: r.state != 'done').write({'state': 'cancel'})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la création pour ajouter des valeurs par défaut intelligentes.
        
        Args:
            vals_list (list): Liste des valeurs pour la création
            
        Returns:
            recordset: Les enregistrements créés
        """
        for vals in vals_list:
            if vals.get('sale_line_id') and not vals.get('sale_order_id'):
                sale_line = self.env['sale.order.line'].browse(vals['sale_line_id'])
                vals['sale_order_id'] = sale_line.order_id.id
                vals['stakeholder_id'] = sale_line.order_id.partner_id.id
        return super().create(vals_list)

    def write(self, vals):
        """Surcharge de l'écriture pour protéger certains champs.
        
        Empêche la modification de champs critiques hors état brouillon.
        
        Args:
            vals (dict): Valeurs à modifier
            
        Raises:
            UserError: Si tentative de modification interdite
            
        Returns:
            bool: True en cas de succès
        """
        protected_fields = ['sale_order_id', 'sale_line_id', 'quantity', 'stakeholder_id']
        if any(field in vals for field in protected_fields):
            if any(record.state != 'draft' for record in self):
                raise UserError(_("Seuls les documents en brouillon peuvent être modifiés"))
        return super().write(vals)

    def unlink(self):
        """Surcharge de la suppression pour contrôler les états.
        
        Raises:
            UserError: Si tentative de suppression interdite
            
        Returns:
            bool: True en cas de succès
        """
        if any(record.state not in ['draft', 'cancel'] for record in self):
            raise UserError(_("Seuls les documents en brouillon ou annulés peuvent être supprimés"))
        return super().unlink()

    def copy(self, default=None):
        """Surcharge de la duplication pour réinitialiser certaines valeurs.
        
        Args:
            default (dict): Valeurs par défaut pour la copie
            
        Returns:
            record: Le nouvel enregistrement créé
        """
        self.ensure_one()
        default = dict(default or {}, state='draft', quantity=1.0)
        return super().copy(default)
