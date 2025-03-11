from odoo import models
from odoo.tools import config
import warnings

# Supprimer le warning spécifique
warnings.filterwarnings('ignore', category=DeprecationWarning, module='odoo.tools.config')

def _warn_deprecated_options(self):
    if 'longpolling_port' in self.options and self.options['longpolling_port'] is not None:
        self.options['gevent_port'] = self.options.pop('longpolling_port')

config._warn_deprecated_options = _warn_deprecated_options 