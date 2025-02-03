# TODO - Module WAF Tempo

## Priorités immédiates
- [ ] Intégrer l'Alsace-Moselle
  - [ ] Ajouter les régions (67, 68, 57)
  - [ ] Configurer les jours fériés spécifiques (Vendredi Saint, 26 décembre)
  - [ ] Adapter les calculs de dates variables pour ces régions

## Améliorations prévues

### Interface utilisateur
- [ ] Ajouter un sélecteur de pays dans la vue calendrier avec widget selection_badge
- [ ] Améliorer la visualisation des jours fériés par région (code couleur, icônes...)
- [ ] Ajouter des tooltips avec plus d'informations au survol des dates
- [ ] Ajouter des icônes pour les jours fériés
  - [ ] Ajouter un champ icon (emoji ou icône)
  - [ ] Exemples généraux (France métropolitaine) :
    - 🎄 Noël
    - 🇫🇷 Fête Nationale
    - ⚔️ Armistice
    - 👥 Fête du Travail
    - 🕊️ Ascension
    - 👼 Toussaint
    - 🌟 Assomption

  - [ ] Spécificités Antilles (971/972) :
    - 🦀 Pâques en Guadeloupe (tradition du crabe)
    - 🍖 Noël (jambon de cochon local)
    - 🌺 Abolition de l'esclavage
    - 🥁 Fête des cuisinières (Guadeloupe)

  - [ ] Alsace-Moselle :
    - ✝️ Vendredi Saint
    - 🎄 Saint-Étienne
    - 🥨 Spécificités locales

  - [ ] Ajouter des icônes dans les vues calendar/list/form
- [ ] Possibilité de personnaliser les icônes par région

### Fonctionnalités
- [ ] Synchronisation avec le module HR pour les congés
- [ ] Calcul automatique des ponts possibles
- [ ] Export iCal des jours fériés
- [ ] API REST pour accéder aux jours fériés

### Données
- [ ] Ajouter plus de régions européennes
- [ ] Support des jours fériés locaux (villes, départements)
- [ ] Historique des jours fériés (dates passées)

### Technique
- [ ] Optimiser les performances de calcul des dates variables
- [ ] Ajouter des tests unitaires
- [ ] Améliorer la documentation technique
- [ ] Gestion des fuseaux horaires pour les DOM-TOM

## Bugs connus
- Aucun pour le moment

## Notes
- Utilisation de workalendar pour les calculs de dates
- Support actuel : France métropolitaine et DOM-TOM uniquement

## Notes importantes pour l'e-commerce DOM-TOM

### Aspects culturels et commerciaux
- [ ] Identifier les périodes de forte activité liées aux traditions locales
  - [ ] Pâques en Guadeloupe → crabes
  - [ ] Noël aux Antilles → jambon local
  - [ ] Autres fêtes traditionnelles à documenter

### Spécificités à prendre en compte
- [ ] Calendrier des fêtes locales
- [ ] Saisonnalité des produits locaux
- [ ] Traditions culinaires spécifiques
- [ ] Périodes de congés locaux

### Adaptations e-commerce nécessaires
- [ ] Système de stock tenant compte des périodes de fête
- [ ] Anticipation des commandes pour les produits festifs
- [ ] Prix adaptés aux périodes (haute/basse saison)
- [ ] Délais de livraison spéciaux pendant les fêtes
- [ ] Messages personnalisés selon les traditions locales

### Méthodologie de recherche
- [ ] Contacter des associations locales
- [ ] Consulter les chambres de commerce
- [ ] Interviewer des commerçants locaux
- [ ] Documenter les retours clients
- [ ] Vérifier toutes les informations avant implémentation

### Documentation à créer
- [ ] Guide des spécificités par région
- [ ] Calendrier commercial adapté
- [ ] Fiches produits avec contexte culturel
- [ ] Guide des bonnes pratiques e-commerce DOM-TOM

## Données à ajouter
[... données Alsace-Moselle ...]

## Améliorations prévues

### Interface utilisateur
- [ ] Ajouter des icônes pour les jours fériés avec personnalisation régionale
  - [ ] Ajouter un champ icon (emoji ou icône)
  - [ ] Exemples généraux (France métropolitaine) :
    - 🎄 Noël
    - 🇫🇷 Fête Nationale
    - ⚔️ Armistice
    - 👥 Fête du Travail
    - 🕊️ Ascension
    - 👼 Toussaint
    - 🌟 Assomption

  - [ ] Spécificités Antilles (971/972) :
    - 🦀 Pâques en Guadeloupe (tradition du crabe)
    - 🍖 Noël (jambon de cochon local)
    - 🌺 Abolition de l'esclavage
    - 🥁 Fête des cuisinières (Guadeloupe)

  - [ ] Alsace-Moselle :
    - ✝️ Vendredi Saint
    - 🎄 Saint-Étienne
    - 🥨 Spécificités locales

  - [ ] Fonctionnalités associées :
    - [ ] Permettre la configuration des icônes par région
    - [ ] Ajouter une description des traditions culinaires et culturelles
    - [ ] Possibilité d'ajouter des photos des plats traditionnels
    - [ ] Lien vers des recettes locales (optionnel)
    - [ ] Support multilingue pour les descriptions
