from odoo import models, fields, api

# Mapping des codes postaux vers (région, département)
ZIP_MAPPING = {
    # DOM-TOM
    '971': ('ROM', '971'),  # Guadeloupe
    '972': ('ROM', '972'),  # Martinique
    '973': ('ROM', '973'),  # Guyane
    '974': ('ROM', '974'),  # La Réunion
    '976': ('ROM', '976'),  # Mayotte
    # Corse (sans département prédéfini)
    '20': ('COR', False),   # Corse (2A ou 2B à sélectionner)
    
    '97': ('ROM', ('Guadeloupe', 'Martinique', 'Guyane', 'La Réunion', 'Mayotte')),
    # Auvergne-Rhône-Alpes (ARA)
    '01': ('ARA', '01'), '03': ('ARA', '03'), '07': ('ARA', '07'),
    '15': ('ARA', '15'), '26': ('ARA', '26'), '38': ('ARA', '38'),
    '42': ('ARA', '42'), '43': ('ARA', '43'), '63': ('ARA', '63'),
    '69': ('ARA', '69'), '73': ('ARA', '73'), '74': ('ARA', '74'),
    # Bourgogne-Franche-Comté (BFC)
    '21': ('BFC', '21'), '25': ('BFC', '25'), '39': ('BFC', '39'),
    '58': ('BFC', '58'), '70': ('BFC', '70'), '71': ('BFC', '71'),
    '89': ('BFC', '89'), '90': ('BFC', '90'),
    # Bretagne (BRE)
    '22': ('BRE', '22'), '29': ('BRE', '29'), '35': ('BRE', '35'),
    '56': ('BRE', '56'),
    # Centre-Val de Loire (CVL)
    '18': ('CVL', '18'), '28': ('CVL', '28'), '36': ('CVL', '36'),
    '37': ('CVL', '37'), '41': ('CVL', '41'), '45': ('CVL', '45'),
    # Grand Est (GES)
    '08': ('GES', '08'), '10': ('GES', '10'), '51': ('GES', '51'),
    '52': ('GES', '52'), '54': ('GES', '54'), '55': ('GES', '55'),
    '57': ('GES', '57'), '67': ('GES', '67'), '68': ('GES', '68'),
    '88': ('GES', '88'),
    # Hauts-de-France (HDF)
    '02': ('HDF', '02'), '59': ('HDF', '59'), '60': ('HDF', '60'),
    '62': ('HDF', '62'), '80': ('HDF', '80'),
    # Île-de-France (IDF)
    '75': ('IDF', '75'), '77': ('IDF', '77'), '78': ('IDF', '78'),
    '91': ('IDF', '91'), '92': ('IDF', '92'), '93': ('IDF', '93'),
    '94': ('IDF', '94'), '95': ('IDF', '95'),
    # Normandie (NOR)
    '14': ('NOR', '14'), '27': ('NOR', '27'), '50': ('NOR', '50'),
    '61': ('NOR', '61'), '76': ('NOR', '76'),
    # Nouvelle-Aquitaine (NAQ)
    '16': ('NAQ', '16'), '17': ('NAQ', '17'), '19': ('NAQ', '19'),
    '23': ('NAQ', '23'), '24': ('NAQ', '24'), '33': ('NAQ', '33'),
    '40': ('NAQ', '40'), '47': ('NAQ', '47'), '64': ('NAQ', '64'),
    '79': ('NAQ', '79'), '86': ('NAQ', '86'), '87': ('NAQ', '87'),
    # Occitanie (OCC)
    '09': ('OCC', '09'), '11': ('OCC', '11'), '12': ('OCC', '12'),
    '30': ('OCC', '30'), '31': ('OCC', '31'), '32': ('OCC', '32'),
    '34': ('OCC', '34'), '46': ('OCC', '46'), '48': ('OCC', '48'),
    '65': ('OCC', '65'), '66': ('OCC', '66'), '81': ('OCC', '81'),
    '82': ('OCC', '82'),
    # Pays de la Loire (PDL)
    '44': ('PDL', '44'), '49': ('PDL', '49'), '53': ('PDL', '53'),
    '72': ('PDL', '72'), '85': ('PDL', '85'),
    # Provence-Alpes-Côte d'Azur (PAC)
    '04': ('PAC', '04'), '05': ('PAC', '05'), '06': ('PAC', '06'),
    '13': ('PAC', '13'), '83': ('PAC', '83'), '84': ('PAC', '84'),
}

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _default_country(self):
        return self.env.ref('base.fr')

    country_id = fields.Many2one(
        default=_default_country,
    )

    region_id = fields.Many2one(
        'res.country.state',
        string='Région',
        domain="[('country_id', '=', country_id), ('parent_id', '=', False)]",
        readonly=True,
    )

    state_id = fields.Many2one(
        'res.country.state',
        string='Département',
        domain="[('country_id', '=', country_id), ('parent_id', '=', region_id)]" 
    )

    @api.onchange('zip', 'country_id', 'city')
    def _onchange_zip_region(self):
        # Réinitialisation des champs
        self.region_id = False
        self.state_id = False

        if not self.zip or not self.country_id or self.country_id != self.env.ref('base.fr'):
            return

        # Validation du format du code postal français (5 chiffres)
        if self.country_id == self.env.ref('base.fr'):
            if not self.zip or len(self.zip) != 5 or not self.zip.isdigit():
                return {
                    'warning': {
                        'title': 'Code postal incorrect',
                        'message': 'Le code postal français doit contenir exactement 5 chiffres.'
                    }
                }

        # Essayer d'abord avec le préfixe précis
        if self.zip.startswith('97') and len(self.zip) >= 3:
            zip_prefix = self.zip[:3]  # 971, 972, etc.
        elif self.zip.startswith('20'):
            zip_prefix = '20'  # Corse
            department_code = False  # On laisse l'utilisateur choisir entre 2A et 2B
        else:
            zip_prefix = self.zip[:2]  # Autres cas

        # Chercher d'abord dans le mapping précis
        if zip_prefix in ZIP_MAPPING:
            region_code, department_code = ZIP_MAPPING[zip_prefix]
        # Sinon, essayer le mapping générique
        elif zip_prefix[:2] in ZIP_MAPPING:
            region_code, department_code = ZIP_MAPPING[zip_prefix[:2]]
        else:
            return {
                'warning': {
                    'title': 'Code postal non reconnu',
                    'message': 'Le code postal saisi ne correspond à aucune région française.'
                }
            }

        region = self.env['res.country.state'].search([
            ('country_id.code', '=', 'FR'),
            ('code', '=', region_code)
        ], limit=1)
        
        if region:
            self.region_id = region.id
            
            # On peut aussi définir directement le département
            if department_code:
                department = self.env['res.country.state'].search([
                    ('country_id.code', '=', 'FR'),
                    ('code', '=', department_code),
                    ('parent_id', '=', region.id)
                ], limit=1)
                if department:
                    self.state_id = department.id
                    return
                
        # Warning pour département manquant seulement si on a un code postal valide
        if self.zip and len(self.zip) == 5 and self.zip.isdigit() and not self.state_id:
            return {
                'warning': {
                    'title': 'Département requis',
                    'message': 'Veuillez sélectionner un département.'
                }
            }

    @api.onchange('country_id')
    def _onchange_country_id(self):
        if self.country_id != self.env.ref('base.fr'):
            self.region_id = False
            self.state_id = False
