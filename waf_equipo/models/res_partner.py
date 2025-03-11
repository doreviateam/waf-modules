from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    partner_blaz_id = fields.Many2one(
        comodel_name='partner.blaz',
        string='Blaz',
        help='Blaz associé au partenaire',
        ondelete='restrict'
    ) 

    # on veut que le nom soit en camel case même quand le séparateur de mot est un tiret ou un espace
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals:
                # Traite chaque mot séparément
                words = []
                for word in vals['name'].split():
                    # Si le mot contient des tirets, on les traite aussi
                    if '-' in word:
                        subwords = word.split('-')
                        word = subwords[0].capitalize() + '-' + '-'.join(w.capitalize() for w in subwords[1:])
                    else:
                        word = word.capitalize()
                    words.append(word)
                # Rejoint les mots avec des espaces
                vals['name'] = ' '.join(words)
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            # Traite chaque mot séparément
            words = []
            for word in vals['name'].split():
                # Si le mot contient des tirets, on les traite aussi
                if '-' in word:
                    subwords = word.split('-')
                    word = subwords[0].capitalize() + '-' + '-'.join(w.capitalize() for w in subwords[1:])
                else:
                    word = word.capitalize()
                words.append(word)
            # Rejoint les mots avec des espaces
            vals['name'] = ' '.join(words)
        return super().write(vals)

    def name_get(self):
        result = []
        for partner in self:
            # Traite chaque mot séparément
            words = []
            for word in partner.name.split():
                # Si le mot contient des tirets, on les traite aussi
                if '-' in word:
                    subwords = word.split('-')
                    word = subwords[0].capitalize() + '-' + '-'.join(w.capitalize() for w in subwords[1:])
                else:
                    word = word.capitalize()
                words.append(word)
            # Rejoint les mots avec des espaces
            result.append((partner.id, ' '.join(words)))
        return result

    