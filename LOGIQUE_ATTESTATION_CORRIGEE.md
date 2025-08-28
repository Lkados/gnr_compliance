# Logique d'Attestation d'Accise - Version Corrigée

## ⚠️ Correction Importante

**ERREUR PRÉCÉDENTE** : J'avais modifié le système pour utiliser des taux fixes basés sur l'attestation.

**LOGIQUE CORRECTE** : Le système doit **calculer le taux réel depuis la facture** et utilise l'attestation uniquement pour :
1. **Affichage** dans l'interface utilisateur
2. **Catégorisation** pour les exports et rapports  
3. **Fallback** uniquement quand aucun taux n'est trouvé dans la facture

## Flux de Calcul du Taux (Ordre de Priorité)

### 1️⃣ **PRIORITÉ 1** : Taxes de la Facture 🏆
- Recherche dans `invoice.taxes` 
- Mots-clés : "gnr", "accise", "ticpe", "gazole", "fioul"
- **Calcul** : `tax_amount ÷ quantity_in_litres`
- **Source** : Vraie ligne de taxe de la facture

### 2️⃣ **PRIORITÉ 2** : Champ Custom de l'Item
- Champ `gnr_tax_rate` sur la ligne d'article
- **Source** : Saisie manuelle sur la facture

### 3️⃣ **PRIORITÉ 3** : Termes/Commentaires Facture  
- Patterns regex : `"3.86€/L"`, `"taxe: 3.86"`, etc.
- **Source** : Zone de commentaires de la facture

### 4️⃣ **PRIORITÉ 4** : Historique Article
- Dernier taux utilisé pour cet article
- **Source** : Mouvements GNR précédents

### 5️⃣ **PRIORITÉ 5** : Article Master
- Champ `gnr_tax_rate` sur la fiche article
- **Source** : Configuration article

### 6️⃣ **DERNIER RECOURS** : Attestation Client 
- **Avec attestation** → 3.86€/L
- **Sans attestation** → 24.81€/L
- **Source** : Fallback uniquement si rien d'autre trouvé

## Rôle de l'Attestation d'Accise

### ✅ **CE QUE FAIT L'ATTESTATION**

1. **Affichage Interface** 📱
   - Banner verte clignotante dans formulaire Client
   - Message "📋 AVEC ATTESTATION"

2. **Catégorisation Client** 📊
   - Champ `customer_category` : "Agricole" / "Autre"
   - Utilisé pour les exports et statistiques

3. **Taux de Fallback** ⚠️
   - **SEULEMENT** si aucun taux trouvé dans la facture
   - Dernière option avant échec complet

### ❌ **CE QUE NE FAIT PAS L'ATTESTATION**

1. **Ne remplace pas** le calcul depuis la facture
2. **Ne force pas** un taux spécifique 
3. **N'ignore pas** les vraies taxes de la facture

## Exemple Concret

### Scenario 1 : Client AVEC Attestation
```
Client: EARL AGRICOLE (attestation complète)
Facture: 
  - Article: FIOUL 1000L
  - Ligne taxe: "Accise GNR - 386€"
  
Calcul: 386€ ÷ 1000L = 0.386€/L
Résultat: taux_gnr = 0.386€/L (depuis la facture)
customer_category = "Agricole" (pour affichage)
```

### Scenario 2 : Client SANS Attestation  
```
Client: TRANSPORT XYZ (sans attestation)
Facture:
  - Article: FIOUL 1000L  
  - Ligne taxe: "Accise GNR - 2481€"

Calcul: 2481€ ÷ 1000L = 2.481€/L
Résultat: taux_gnr = 2.481€/L (depuis la facture)
customer_category = "Autre" (pour affichage)
```

### Scenario 3 : Aucun Taux dans Facture (Fallback)
```
Client: EARL AGRICOLE (attestation complète)
Facture: 
  - Article: FIOUL 1000L
  - Aucune ligne de taxe GNR trouvée
  - Aucun taux dans commentaires
  
Fallback: customer_category = "Agricole" → 3.86€/L
Résultat: taux_gnr = 3.86€/L (fallback basé attestation)
⚠️ Log d'avertissement généré
```

## Code Corrigé

### Fonction Principale (Corrrigée) ✅
```python
def capture_vente_gnr(doc, method):
    # 1. Déterminer catégorie client (pour affichage)
    customer_category = determine_customer_category_from_attestation(doc.customer)
    
    # 2. Calculer le VRAI taux depuis la facture
    taux_gnr_reel = get_real_gnr_tax_from_invoice(item, doc)  # ← PRIORITÉ 1-5
    
    # 3. Créer mouvement avec taux réel
    mouvement.update({
        "taux_gnr": taux_gnr_reel,  # ← TAUX RÉEL DE LA FACTURE
        "customer_category": customer_category,  # ← POUR AFFICHAGE SEULEMENT
        "montant_taxe_gnr": quantity_in_litres * taux_gnr_reel
    })
```

### Fonction de Fallback (Corrigée) ✅  
```python
def get_real_gnr_tax_from_invoice(item, invoice_doc):
    # Priorités 1-5 : Calculs depuis facture...
    
    # DERNIER RECOURS : Attestation comme fallback
    try:
        customer_category = determine_customer_category_from_attestation(invoice_doc.customer)
        fallback_rate = get_tax_rate_from_customer_category(customer_category)
        frappe.logger().warning(f"Fallback vers attestation: {fallback_rate}€/L")
        return fallback_rate
    except:
        return 24.81  # Taux standard absolu
```

## Validation du Système Corrigé

### Tests à Effectuer ✅

1. **Facture avec taxe GNR explicite**
   - Vérifier que le taux calculé = taxe ÷ quantité
   - customer_category pour affichage uniquement

2. **Facture sans taxe GNR**  
   - Vérifier utilisation du fallback basé sur attestation
   - Log d'avertissement présent

3. **Client avec/sans attestation**
   - Banner d'affichage correct
   - Catégorisation pour export correcte
   - Taux toujours calculé depuis facture en priorité

## Résumé ✅

**L'attestation d'accise** est un **indicateur** qui :
- **Informe** l'utilisateur visuellement  
- **Catégorise** le client pour les rapports
- **Sert de fallback** uniquement en dernier recours

**Le taux GNR** est **toujours calculé depuis la facture** en priorité, selon les 6 niveaux de priorité définis.