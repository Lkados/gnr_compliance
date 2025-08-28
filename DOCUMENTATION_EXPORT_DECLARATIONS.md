# Export des Déclarations GNR - Format Officiel

## Vue d'ensemble

Le système GNR Compliance génère maintenant les déclarations officielles avec **exactement le même format et la même mise en page** que les fichiers originaux fournis par les autorités.

## Types de Déclarations Disponibles

### 1. Arrêté Trimestriel de Stock
- **Format**: Excel (.xlsx) 
- **Fréquence**: Trimestrielle
- **Contenu**: Comptabilité matière jour par jour
- **Caractéristiques**:
  - Structure identique au format DGDDI
  - Formules Excel automatiques pour calculs de stock
  - Largeurs de colonnes exactes (A: 17.7cm, B-G: 11.7cm)
  - Hauteurs de lignes personnalisées
  - Fusions de cellules conformes
  - En-têtes avec société et numéro d'autorisation

### 2. Liste Semestrielle des Clients  
- **Format**: Excel (.xlsx)
- **Fréquence**: Semestrielle
- **Contenu**: Liste des clients avec volumes et tarifs
- **Caractéristiques**:
  - Format officiel douanier
  - 400+ colonnes comme le template original
  - Largeurs exactes: A(32.7cm), C(47.6cm), E&F(34.7cm)
  - Tarifs automatiques: 3.86€/hL (agricole), 24.81€/hL (autres)
  - Volumes en hectolitres (conversion automatique)

## Comment Utiliser le Système

### Méthode 1: Depuis la Liste des Mouvements GNR

1. **Naviguer vers**: Liste des Mouvements GNR
2. **Cliquer sur**: Bouton "Exporter Déclarations Officielles" (bouton principal bleu)
3. **Sélectionner**: 
   - Type de déclaration (Arrêté Trimestriel ou Liste Clients)
   - Période (prédéfinie ou personnalisée)
4. **Prévisualiser**: Cliquer sur "Prévisualiser" pour voir les données
5. **Générer**: Cliquer sur "Générer et Télécharger"

### Méthode 2: Depuis un Mouvement GNR Individuel

1. **Ouvrir**: Un mouvement GNR validé
2. **Cliquer sur**: Menu "Actions" → "Générer Déclarations"
3. **Suivre**: Les mêmes étapes que ci-dessus

### Méthode 3: Raccourcis Clavier

- **Ctrl + E**: Ouvrir la boîte de dialogue d'export
- **Ctrl + S**: Soumettre tous les mouvements en brouillon

## Fonctionnalités de l'Interface

### Dialog d'Export Avancé

1. **Type de Déclaration**
   - Sélection entre Arrêté Trimestriel et Liste Clients
   - Informations contextuelles automatiques

2. **Sélection de Période**
   - **Prédéfinie**: Trimestres/semestres disponibles basés sur les données
   - **Personnalisée**: Dates de début/fin libres

3. **Prévisualisation en Temps Réel**
   - Résumé des mouvements de stock
   - Liste des premiers clients
   - Statistiques (volumes, nombre d'opérations)

4. **Génération et Téléchargement**
   - Indicateur de progression
   - Téléchargement automatique
   - Noms de fichiers conformes au standard

### Fonctionnalités Additionnelles

- **Statistiques GNR**: Sidebar avec stock actuel, entrées/sorties mensuelles
- **Vérification de Cohérence**: Bouton pour valider les données
- **Soumission en Lot**: Soumettre tous les brouillons d'un coup
- **Indicateurs Visuels**: Codes couleur pour catégories clients et types d'opération

## API et Intégration Technique

### Endpoints Disponibles

```python
# Télécharger arrêté trimestriel
frappe.call({
    method: 'gnr_compliance.api_excel.download_arrete_trimestriel',
    args: {
        quarter: 1,
        year: 2025,
        // ou period_start: '2025-01-01', period_end: '2025-03-31'
    }
});

# Télécharger liste clients
frappe.call({
    method: 'gnr_compliance.api_excel.download_liste_clients', 
    args: {
        semester: 2,
        year: 2024,
        // ou period_start: '2024-07-01', period_end: '2024-12-31'
    }
});

# Prévisualiser les données
frappe.call({
    method: 'gnr_compliance.api_excel.preview_declaration_data',
    args: {
        declaration_type: 'arrete_trimestriel', // ou 'liste_clients'
        period_start: '2025-01-01',
        period_end: '2025-03-31'
    }
});

# Récupérer les périodes disponibles
frappe.call({
    method: 'gnr_compliance.api_excel.get_available_periods'
});
```

### Classes Python Principales

```python
# Générateur d'arrêté trimestriel
from gnr_compliance.utils.excel_generators import ArreteTrimestrielGenerator
generator = ArreteTrimestrielGenerator()
excel_data = generator.generate(period_start, period_end, company_name, autorisation_number, stock_movements)

# Générateur de liste clients  
from gnr_compliance.utils.excel_generators import ListeClientsGenerator
generator = ListeClientsGenerator()
excel_data = generator.generate(period_start, period_end, company_name, company_siren, clients_data)
```

## Conformité Réglementaire

### Arrêté Trimestriel
- ✅ **Format DGDDI**: Conforme aux spécifications officielles
- ✅ **Calculs Automatiques**: Formules Excel pour stocks finaux
- ✅ **Structure**: En-têtes, colonnes et mise en page identiques
- ✅ **Dates**: Conversion automatique format Excel (numéros de série)
- ✅ **Cumuls**: Totaux trimestriels et récapitulatif final

### Liste Clients
- ✅ **Format Douanier**: Structure conforme aux exigences douanes
- ✅ **Tarification**: Application automatique des taux d'accise
- ✅ **Conversion d'Unités**: Litres → hectolitres automatique
- ✅ **Template Large**: 400+ colonnes comme requis
- ✅ **Informations Complètes**: SIREN, volumes, tarifs

## Exemple de Noms de Fichiers Générés

```
TIPAccEne - Arrêté Trimestriel de Stock - Détaillé - 2025 Janvier à Mars.xlsx
TIPAccEne - Liste Semestrielle des Clients - Douane - 2024 Juillet à Décembre.xlsx
```

## Tests et Validation

Le système a été testé avec :
- ✅ **Structures identiques**: Comparaison directe avec les originaux
- ✅ **Largeurs de colonnes**: Précision au centième
- ✅ **Hauteurs de lignes**: Reproduction exacte
- ✅ **Formules Excel**: Calculs conformes
- ✅ **Fusions de cellules**: Identiques aux originaux
- ✅ **Formatage**: Police, alignement, bordures
- ✅ **Données de test**: Validation avec données réelles

## Fichiers de Test Générés

Pour validation:
- `TEST_Arrêté_Trimestriel_Format_Exact.xlsx`
- `TEST_Liste_Clients_Format_Exact.xlsx`

Ces fichiers peuvent être comparés directement avec les originaux pour vérifier la conformité parfaite du format.

## Support et Maintenance

- **Logs**: Toutes les générations sont tracées
- **Validation**: Vérification automatique des données avant export
- **Erreurs**: Messages d'erreur explicites en cas de problème
- **Performance**: Génération optimisée même pour de gros volumes

## Configuration Requise

- **Frappe Framework**: Version compatible ERPNext
- **Python**: Modules openpyxl installés
- **Données**: Mouvements GNR validés dans le système
- **Paramètres**: Société et numéro d'autorisation configurés