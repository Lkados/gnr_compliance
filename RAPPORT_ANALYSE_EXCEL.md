# Analyse des Fichiers Excel - Formats GNR

## Vue d'ensemble

J'ai analysé les deux fichiers Excel fournis pour comprendre leur format et leur mise en page :

1. **TIPAccEne - Arrêté Trimestriel de Stock - Détaillé - 2025 Janvier à Mars.Xlsx**
2. **TIPAccEne - Liste Semestrielle des Clients - Douane - 2024 Juillet à Décembre.Xlsx**

## FICHIER 1: Arrêté Trimestriel de Stock

### Structure générale
- **Type**: Comptabilité matière pour Gasoil Non Routier (GNR)
- **Période**: 1er Trimestre 2025 (Janvier - Février - Mars)
- **Société**: ETS STEPHANE JOSSEAUME
- **Numéro d'autorisation**: 08/2024/AMIENS

### Format et colonnes

#### En-têtes principaux (lignes 1-4):
- Ligne 1: "Comptabilité Matière - Gasoil Non Routier" (fusionnée A1:G1)
- Ligne 2: "Société : ETS STEPHANE JOSSEAUME" (fusionnée A2:G2)
- Ligne 3: "Numéro d'autorisation : 08/2024/AMIENS" (fusionnée A3:G3)
- Ligne 4: "1er Trimestre 2025 (Janvier - Février - Mars)" (fusionnée A4:G4)
- Ligne 6: "Volume réel en Litres" (fusionnée B6:G6)

#### Structure des colonnes (lignes 7-8):
- **Colonne A**: Date (format numérique Excel)
- **Colonne B**: Stock Initial
- **Colonne C**: Entrées (avec sous-colonnes N° BL)
- **Colonne D**: Volume des entrées
- **Colonne E**: Sorties - Volume AGRICOLE/FORESTIER
- **Colonne F**: Sorties - Volume Sans Attestation
- **Colonne G**: Stock Final (calculé automatiquement)

#### Données (lignes 9+):
- Chaque ligne représente une journée
- Dates en format Excel (45659 = ~1er janvier 2025)
- Formules automatiques pour le stock final: `B + D - E - F`
- Volumes en litres
- Stock final reporté automatiquement comme stock initial du jour suivant

#### Pied de page (lignes 68+):
- Ligne 68: Cumul trimestriel des entrées et sorties
- Lignes 70-72: Résumé final avec stock comptable, stock physique et écart

### Caractéristiques techniques:
- **Nombre de lignes de données**: ~60 jours
- **Formules Excel**: Calculs automatiques des stocks
- **Format des cellules**: Nombres avec formatage personnalisé
- **Fusions de cellules**: En-têtes et sous-en-têtes
- **Largeurs de colonnes**: Personnalisées (A: 17.7, B-G: 11.7)

## FICHIER 2: Liste Semestrielle des Clients

### Structure générale
- **Type**: Base de données clients et fournisseurs
- **Période**: 2ème semestre 2024 (Juillet à Décembre)
- **Usage**: Déclarations douanières GNR

### Format et colonnes

#### En-têtes (lignes 1-2):
- Ligne 1: 
  - Colonne A: "Informations distributeur autorisé ou fournisseur"
  - Colonne C: "Informations client"  
  - Colonne E: "Données carburant GNR"

- Ligne 2:
  - Colonne A: "Raison sociale"
  - Colonne B: "SIREN"
  - Colonne C: "Raison sociale du client"
  - Colonne D: "SIREN du client"
  - Colonne E: "Volumes (en hL) de GNR livrés au client au cours du dernier semestre civil écoulé"
  - Colonne F: "Tarif d'accise appliqué (en euro par hectolitres)"

#### Données (lignes 3+):
- **Colonne A**: Toujours "ETS STEPHANE JOSSEAUME" (distributeur)
- **Colonne B**: SIREN distributeur (vide dans l'exemple)
- **Colonne C**: Raison sociale du client
- **Colonne D**: SIREN du client
- **Colonne E**: Volume livré en hectolitres (hL)
- **Colonne F**: Tarif d'accise (€/hL) - deux taux principaux:
  - **24.81 €/hL**: Pour clients professionnels (transport, etc.)
  - **3.86 €/hL**: Pour secteur agricole/forestier

### Exemples de clients:
- COLDEFY IPFAC (898 087 903): 20 hL à 24.81 €/hL
- EARL ARSTIVELL (402 263 115): 40 hL à 3.86 €/hL
- EARL AU GRE DU VENT (380 923 870): 152.77 hL à 3.86 €/hL

### Caractéristiques techniques:
- **Nombre de lignes de données**: ~100+ clients
- **Largeur de colonnes**: 
  - A: 32.7 (raison sociale distributeur)
  - C: 47.6 (raison sociale client)
  - E: 34.7 (volumes)
  - F: 34.7 (tarifs)
- **Format très large**: 400+ colonnes potentielles dans le template
- **Types de clients**: EARL, SARL, SAS, Mairies, Entreprises, particuliers

## Observations importantes

### Cohérence entre les fichiers:
1. **Même société**: ETS STEPHANE JOSSEAUME dans les deux fichiers
2. **Même autorisation**: 08/2024/AMIENS
3. **Volumes cohérents**: Les sorties du fichier 1 correspondent aux livraisons du fichier 2

### Formats réglementaires:
- **Arrêté Trimestriel**: Format de comptabilité matière obligatoire
- **Liste Clients**: Format pour déclarations douanières semestrielles
- **Unités**: Litres pour le stock, hectolitres pour les déclarations clients

### Structure des données:
- **Journal chronologique** pour le stock (fichier 1)
- **Base de données relationnelle** pour les clients (fichier 2)
- **Calculs automatiques** dans le fichier stock
- **Classification tarifaire** automatique selon le type de client

Ces formats correspondent aux obligations réglementaires françaises pour les distributeurs de GNR (Gasoil Non Routier).