# GNR Compliance - Application ERPNext

![Version](https://img.shields.io/badge/version-1.1.0-green) ![Frappe](https://img.shields.io/badge/Frappe-v15-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## 📋 Table des matières

- [Description](#description)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Modules](#modules)
- [API](#api)
- [Développement](#développement)
- [Tests](#tests)
- [Déploiement](#déploiement)
- [Troubleshooting](#troubleshooting)
- [Contribution](#contribution)
- [Licence](#licence)

## 🎯 Description

**GNR Compliance** est une application ERPNext spécialisée dans la gestion de la conformité réglementaire française pour les **Gazoles Non Routiers (GNR)** et produits pétroliers. Développée par Mohamed Kachtit pour **Josseaume Énergies**, cette application automatise le suivi fiscal, les déclarations périodiques et la gestion des taxes TICPE.

### 🏢 Contexte métier

L'application répond aux obligations réglementaires françaises concernant :
- La taxe intérieure de consommation sur les produits énergétiques (TICPE)
- Les déclarations trimestrielles et semestrielles obligatoires
- Le suivi des volumes et taxes pour différents types de carburants
- La gestion des attestations clients pour les exonérations

## ✨ Fonctionnalités

### 🔄 Traçabilité automatique
- **Capture automatique** des ventes, achats et mouvements de stock
- **Détection intelligente** des produits GNR par groupe d'articles
- **Calcul automatique** des taxes à partir des factures réelles
- **Conversion automatique** d'unités (L, hL, m³, kg, T)

### 📊 Gestion déclarative
- **Déclarations périodiques** automatisées (trimestrielles, semestrielles, annuelles)
- **Calculs de taxes** conformes à la réglementation
- **Exportations multi-formats** (Excel, CSV, PDF, XML)
- **Rapports d'analyse** détaillés

### 🎛️ Interface utilisateur
- **Interfaces ergonomiques** intégrées à ERPNext
- **Tableaux de bord** temps réel
- **Alertes et notifications** contextuelles
- **Outils de correction** et d'audit

### 🔒 Conformité et audit
- **Traçabilité complète** des modifications
- **Logs d'audit** détaillés
- **Contrôles de cohérence** automatiques
- **Sauvegarde des états** déclaratifs

## 🏗️ Architecture

### Structure du projet
```
gnr_compliance/
├── gnr_compliance/                 # Module principal
│   ├── __init__.py
│   ├── api.py                     # APIs publiques
│   ├── hooks.py                   # Configuration ERPNext
│   ├── config/                    # Configuration app
│   ├── gnr_compliance/            # Sous-module métier
│   │   ├── doctype/              # Types de documents
│   │   │   ├── declaration_periode_gnr/    # Déclarations
│   │   │   └── mouvement_gnr/             # Mouvements
│   │   └── __init__.py
│   ├── integrations/              # Intégrations ERPNext
│   │   ├── sales.py              # Factures de vente
│   │   └── stock.py              # Mouvements de stock
│   ├── overrides/                 # Surcharges ERPNext
│   │   ├── purchase_invoice.py   # Factures d'achat
│   │   └── sales_invoice.py      # Factures de vente
│   ├── patches/                   # Scripts de migration
│   ├── public/                    # Assets frontend
│   │   ├── css/                  # Styles personnalisés
│   │   └── js/                   # Scripts client
│   ├── report/                    # Rapports personnalisés
│   ├── setup/                     # Scripts d'installation
│   ├── templates/                 # Templates web
│   └── utils/                     # Utilitaires
├── install_script.sh              # Script d'installation Docker
├── pyproject.toml                 # Configuration Python
└── license.txt                    # Licence MIT
```

### 🎯 DocTypes principaux

#### Mouvement GNR
Enregistre tous les mouvements de produits GNR :
```json
{
  "fields": [
    "type_mouvement",      // Vente/Achat/Stock/Transfert
    "date_mouvement",      // Date de l'opération
    "code_produit",        // Référence article
    "quantite",            // Quantité en litres
    "prix_unitaire",       // Prix par litre
    "taux_gnr",            // Taux de taxe (€/L)
    "montant_taxe_gnr",    // Montant de taxe calculé
    "client",              // Client (si vente)
    "fournisseur",         // Fournisseur (si achat)
    "reference_document",   // Type de document source
    "reference_name",      // Nom du document source
    "categorie_gnr",       // Catégorie du produit
    "trimestre",           // Trimestre comptable
    "semestre",            // Semestre comptable
    "annee"                // Année comptable
  ]
}
```

#### Déclaration Période GNR
Centralise les déclarations périodiques :
```json
{
  "autoname": "format:DECL-{type_periode}-{periode}-{annee}",
  "fields": [
    "type_periode",        // Trimestriel/Semestriel/Annuel
    "periode",             // T1/T2/T3/T4 ou S1/S2 ou ANNEE
    "annee",               // Année de déclaration
    "statut",              // Brouillon/Soumise/Validée/Transmise
    "total_ventes",        // Volume total vendu (L)
    "total_taxe_gnr",      // Taxe totale (€)
    "nb_clients",          // Nombre de clients
    "volume_avec_attestation",  // Volume exonéré (L)
    "volume_sans_attestation"   // Volume taxé (L)
  ]
}
```

### 🔗 Intégrations ERPNext

#### Sales Invoice
```python
doc_events = {
    "Sales Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_vente_gnr",
        "on_cancel": "gnr_compliance.integrations.sales.cleanup_after_cancel"
    }
}
```

#### Purchase Invoice
```python
doc_events = {
    "Purchase Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_achat_gnr", 
        "on_cancel": "gnr_compliance.integrations.sales.cleanup_after_cancel_purchase"
    }
}
```

#### Stock Entry
```python
doc_events = {
    "Stock Entry": {
        "on_submit": "gnr_compliance.integrations.stock.capture_mouvement_stock",
        "before_cancel": "gnr_compliance.integrations.stock.cancel_mouvement_stock"
    }
}
```

## 🚀 Installation

### Pré-requis
- **ERPNext v15+** avec Frappe Framework
- **Python 3.10+**
- **Docker** (pour installation automatisée)
- **Git** pour le versioning

### Installation automatique (recommandée)
```bash
# Cloner le dépôt
git clone https://github.com/Lkados/gnr_compliance.git
cd gnr_compliance

# Exécuter l'installation automatisée
chmod +x install_script.sh
./install_script.sh
```

### Installation manuelle
```bash
# Depuis votre bench ERPNext
cd /path/to/frappe-bench

# Récupérer l'application
bench get-app https://github.com/Lkados/gnr_compliance

# Installer sur votre site
bench --site [votre-site] install-app gnr_compliance

# Migrer la base de données
bench --site [votre-site] migrate
```

### Installation de développement
```bash
# Mode développement
bench get-app https://github.com/Lkados/gnr_compliance --branch develop
bench --site [votre-site] install-app gnr_compliance

# Installer pre-commit
cd apps/gnr_compliance
pre-commit install
```

## ⚙️ Configuration

### 1. Configuration des articles
Marquez vos articles comme produits GNR :
- Accédez à **Stock > Articles**
- Cochez **"Article GNR Tracké"**
- Définissez la **catégorie GNR** et le **taux de taxe**

### 2. Groupes d'articles auto-détectés
Les groupes suivants sont automatiquement reconnus :
- `Combustibles/Carburants/GNR`
- `Combustibles/Carburants/Gazole` 
- `Combustibles/Adblue`
- `Combustibles/Fioul/Bio`
- `Combustibles/Fioul/Hiver`
- `Combustibles/Fioul/Standard`

### 3. Taux de taxes par défaut
```python
default_rates = {
    "ADBLUE": 0.0,          # AdBlue non taxé
    "FIOUL_BIO": 3.86,      # Fioul agricole bio
    "FIOUL_HIVER": 3.86,    # Fioul agricole hiver  
    "FIOUL_STANDARD": 3.86, # Fioul agricole standard
    "GAZOLE": 24.81,        # Gazole routier
    "GNR": 24.81,           # GNR standard
}
```

### 4. Champs personnalisés
L'application ajoute automatiquement des champs aux DocTypes ERPNext :

#### Item
- `is_gnr_tracked` : Article GNR tracé
- `gnr_tracked_category` : Catégorie GNR
- `gnr_tax_rate` : Taux de taxe (€/hL)

#### Stock Entry  
- `gnr_items_detected` : Nombre d'articles GNR
- `gnr_categories_processed` : Traitement effectué

## 📈 Utilisation

### 1. Workflow automatique

#### Lors d'une facture de vente :
1. **Détection** automatique des articles GNR
2. **Récupération** du taux réel depuis la facture
3. **Conversion** en litres si nécessaire
4. **Création** du mouvement GNR
5. **Calcul** de la taxe correspondante

#### Lors d'un mouvement de stock :
1. **Analyse** des articles dans le Stock Entry
2. **Détermination** du type de mouvement
3. **Application** du taux configuré
4. **Traçabilité** complète du flux

### 2. Déclarations périodiques

#### Créer une déclaration :
```python
# Via l'interface
GNR Compliance > Déclaration Période GNR > Nouveau

# Via API
declaration = frappe.new_doc("Declaration Periode GNR")
declaration.type_periode = "Trimestriel"
declaration.periode = "T1" 
declaration.annee = 2024
declaration.insert()
declaration.submit()
```

#### Exporter les données :
```python
# Appel API pour export Excel
frappe.call({
    method: "gnr_compliance.api.generate_export",
    args: {
        export_format: "Excel Arrêté Trimestriel",
        from_date: "2024-01-01",
        to_date: "2024-03-31",
        periode_type: "Trimestrielle",
        inclure_details: true
    }
})
```

### 3. Tableaux de bord

#### Métriques temps réel :
- Volume total vendu par période
- Montant des taxes collectées
- Répartition par catégorie de produit
- Top clients par volume

#### Alertes et contrôles :
- Articles sans taux configuré
- Incohérences de calcul
- Déclarations en retard
- Mouvements non traités

## 🔌 API

### Endpoints principaux

#### Export de données
```python
@frappe.whitelist()
def generate_export(export_format, from_date, to_date, periode_type="Trimestrielle", inclure_details=False):
    """Génère un export dans le format demandé"""
    # Formats supportés : Excel, CSV, PDF, XML
```

#### Recalcul des taux
```python
@frappe.whitelist()  
def recalculer_tous_les_taux_reels_factures(limite=100):
    """Recalcule les mouvements avec des taux suspects"""
```

#### Retraitement des stocks
```python
@frappe.whitelist()
def reprocess_stock_entries(from_date=None, to_date=None):
    """Retraite les Stock Entry manqués"""
```

#### Analyse qualité
```python
@frappe.whitelist()
def analyser_qualite_taux_factures():
    """Analyse la qualité des taux appliqués"""
```

### Utilitaires de conversion
```python
from gnr_compliance.utils.unit_conversions import convert_to_litres

# Conversions supportées
quantity_l = convert_to_litres(100, "hL")  # 100 hL = 10000 L
quantity_l = convert_to_litres(1, "m³")    # 1 m³ = 1000 L  
quantity_l = convert_to_litres(850, "kg")  # 850 kg ≈ 1000 L (densité 0.85)
```

## 🛠️ Développement

### Structure de développement
```bash
# Environnement de développement
cd apps/gnr_compliance

# Installer les dépendances de développement  
pip install -e .
pre-commit install

# Lancer les tests
bench --site [site] run-tests --app gnr_compliance

# Générer la documentation
bench --site [site] build-docs gnr_compliance
```

### Standards de code
- **Ruff** pour le formatage Python
- **ESLint + Prettier** pour JavaScript
- **Pre-commit hooks** obligatoires
- **Type hints** Python recommandés

### Tests et qualité
```bash
# Tests unitaires
bench --site test_site run-tests --app gnr_compliance --module gnr_compliance.tests

# Vérification qualité
ruff check gnr_compliance/
ruff format gnr_compliance/

# Tests de performance
bench --site test_site run-tests --app gnr_compliance --profile
```

## 🧪 Tests

### Structure des tests
```
gnr_compliance/tests/
├── test_integrations.py      # Tests intégrations ERPNext
├── test_api.py              # Tests API endpoints  
├── test_calculations.py     # Tests calculs taxes
├── test_conversions.py      # Tests conversions unités
└── test_exports.py          # Tests formats export
```

### Exécution des tests
```bash
# Tous les tests
bench --site test_site run-tests --app gnr_compliance

# Tests spécifiques
bench --site test_site run-tests --app gnr_compliance --module gnr_compliance.tests.test_calculations

# Tests avec couverture
bench --site test_site run-tests --app gnr_compliance --coverage
```

## 🚢 Déploiement

### Environnement de production

#### Via Docker (recommandé)
```bash
# Le script install_script.sh gère :
# - La suppression des anciennes versions
# - L'installation sur tous les conteneurs
# - La migration de base de données
# - Le redémarrage des services
```

#### Manuel
```bash
# Sur le serveur de production
cd /home/frappe/frappe-bench

# Mise à jour
bench get-app https://github.com/Lkados/gnr_compliance
bench --site erp.josseaume-energies.com migrate
bench restart
```

### Configuration production
- **Logs structurés** via Frappe Logger
- **Monitoring** des performances
- **Sauvegarde** automatique des déclarations
- **Alertes** par email en cas d'erreur

## 🔧 Troubleshooting

### Problèmes courants

#### Articles non détectés
```python
# Vérifier la configuration
frappe.get_value("Item", "CODE_ARTICLE", ["is_gnr_tracked", "item_group"])

# Forcer la détection
gnr_compliance.integrations.sales.check_if_gnr_item_for_sales("CODE_ARTICLE")
```

#### Taux incorrects  
```python
# Analyser la qualité des taux
frappe.call("gnr_compliance.integrations.sales.analyser_qualite_taux_factures")

# Recalculer depuis les factures
frappe.call("gnr_compliance.integrations.sales.recalculer_tous_les_taux_reels_factures")
```

#### Mouvements manqués
```python  
# Retraiter les stocks
frappe.call("gnr_compliance.integrations.stock.reprocess_stock_entries", {
    "from_date": "2024-01-01",
    "to_date": "2024-12-31"
})
```

### Logs et debugging
```python
# Activer les logs détaillés
frappe.logger().setLevel(logging.DEBUG)

# Consulter les logs spécifiques
grep "[GNR]" /home/frappe/frappe-bench/logs/worker.log

# Debug d'un Stock Entry spécifique  
frappe.call("gnr_compliance.integrations.stock.debug_stock_entry", "STE-2024-00001")
```

## 🤝 Contribution

### Processus de contribution
1. **Fork** le projet
2. Créer une **branche feature** : `git checkout -b feature/ma-fonctionnalite`
3. **Commiter** : `git commit -m 'feat: nouvelle fonctionnalité'`
4. **Push** : `git push origin feature/ma-fonctionnalite`
5. Ouvrir une **Pull Request**

### Standards de commit
- `feat:` nouvelle fonctionnalité
- `fix:` correction de bug
- `docs:` documentation
- `style:` formatage
- `refactor:` refactoring
- `test:` tests
- `chore:` maintenance

### Contact développeur
- **Nom** : Mohamed Kachtit
- **Email** : mokachtit@gmail.com
- **GitHub** : [@Lkados](https://github.com/Lkados)

## 📄 Licence

Ce projet est sous licence **MIT** - voir le fichier [license.txt](license.txt) pour plus de détails.

---

## 📊 Informations techniques

- **Version** : 1.1.0
- **Compatibilité** : ERPNext v15+, Frappe Framework
- **Python** : 3.10+
- **Base de données** : MariaDB/MySQL
- **Frontend** : JavaScript ES6+, HTML5, CSS3
- **Outils** : Ruff, ESLint, Prettier, Pre-commit

## 🎯 Roadmap

### Version 1.2.0 (Q2 2024)
- [ ] Interface mobile responsive
- [ ] Export EDI normalisé
- [ ] Intégration comptabilité analytique
- [ ] Rapports Power BI

### Version 1.3.0 (Q3 2024)  
- [ ] API REST complète
- [ ] Workflow d'approbation
- [ ] Notifications avancées
- [ ] Archivage automatique

---

*Dernière mise à jour : 28 Août 2025*
*Documentation générée automatiquement par Claude Code*