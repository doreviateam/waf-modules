"""
Mixins WAF Preso
==============

Ce package contient les mixins spécifiques au module WAF Preso.
Ces mixins étendent les fonctionnalités des mixins WAF Core.

Mixins disponibles :
------------------
- dispatch_mixin: Gestion des dispatches et stocks
- partner_mixin: Gestion des partenaires et adresses
- sequence_mixin: Gestion des séquences et références

Ces mixins héritent et étendent les fonctionnalités de :
- waf.state.tracking (waf_core)
- address.validation.mixin (waf_localisation)
- business.day.mixin (waf_tempo)
"""

from . import dispatch_mixin
from . import partner_mixin
from . import sequence_mixin
