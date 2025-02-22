from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Constantes
    REGION_MAPPING = {
        # Régions métropolitaines
        'ARA': ['01', '03', '07', '15', '26', '38', '42', '43', '63', '69', '73', '74'],
        'BFC': ['21', '25', '39', '58', '70', '71', '89', '90'],
        'BRE': ['22', '29', '35', '56'],
        'CVL': ['18', '28', '36', '37', '41', '45'],
        'GES': ['08', '10', '51', '52', '54', '55', '57', '67', '68', '88'],
        'HDF': ['02', '59', '60', '62', '80'],
        'IDF': ['75', '77', '78', '91', '92', '93', '94', '95'],
        'NOR': ['14', '27', '50', '61', '76'],
        'NAQ': ['16', '17', '19', '23', '24', '33', '40', '47', '64', '79', '86', '87'],
        'OCC': ['09', '11', '12', '30', '31', '32', '34', '46', '48', '65', '66', '81', '82'],
        'PDL': ['44', '49', '53', '72', '85'],
        'PAC': ['04', '05', '06', '13', '83', '84'],
        'COR': ['2A', '2B'],
        # Régions d'outre-mer
        'ROM': ['971', '972', '973', '974', '976']
    }

    # Champs
    country_id = fields.Many2one(
        default=lambda self: self.env.ref('base.fr'),
    )

    region_id = fields.Many2one(
        'res.country.state',
        string='Région',
        domain="[('country_id', '=', country_id), ('is_region', '=', True)]",
        tracking=True,
    )

    state_id = fields.Many2one(
        'res.country.state',
        string='Département',
        domain="[('country_id', '=', country_id), ('parent_id', '=', region_id)]",
        tracking=True,
    )

    @api.onchange('zip', 'country_id')
    def _onchange_zip_region(self):
        """Détermine la région et le département en fonction du code postal"""
        self.region_id = self.state_id = False
        
        if not self.zip or self.country_id != self.env.ref('base.fr'):
            return

        if not self._validate_french_zip():
            return self._warning_message('Code postal incorrect', 
                'Le code postal français doit contenir exactement 5 chiffres.')

        region_code, dept_code = self._get_region_dept_codes()
        if not region_code:
            return self._warning_message('Code postal non reconnu',
                'Le code postal saisi ne correspond à aucune région française.')

        self._set_region_and_department(region_code, dept_code)

    def _validate_french_zip(self):
        """Valide le format du code postal français"""
        return bool(self.zip and len(self.zip) == 5 and self.zip.isdigit())

    def _get_region_dept_codes(self):
        """Détermine les codes de région et département"""
        zip_prefix = self.zip[:3] if self.zip.startswith('97') else self.zip[:2]
        
        for region_code, departments in self.REGION_MAPPING.items():
            if zip_prefix in departments:
                return region_code, zip_prefix
            # Cas spécial Corse
            elif zip_prefix == '20':
                return 'COR', False
        return False, False

    def _set_region_and_department(self, region_code, dept_code):
        """Définit la région et le département"""
        region = self.env['res.country.state'].search([
            ('country_id.code', '=', 'FR'),
            ('code', '=', region_code),
            ('is_region', '=', True)
        ], limit=1)

        if region:
            self.region_id = region.id
            if dept_code:
                department = self.env['res.country.state'].search([
                    ('country_id.code', '=', 'FR'),
                    ('code', '=', dept_code),
                    ('parent_id', '=', region.id)
                ], limit=1)
                if department:
                    self.state_id = department.id
                else:
                    return self._warning_message('Département requis',
                        'Veuillez sélectionner un département.')

    def _warning_message(self, title, message):
        """Retourne un message d'avertissement formaté"""
        return {
            'warning': {
                'title': title,
                'message': message
            }
        }

    @api.onchange('country_id')
    def _onchange_country_id(self):
        """Réinitialise région et département si pays différent de France"""
        if self.country_id != self.env.ref('base.fr'):
            self.region_id = self.state_id = False