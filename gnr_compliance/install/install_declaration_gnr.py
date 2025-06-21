# Installation script pour les nouvelles déclarations GNR
# À exécuter dans la console ERPNext ou comme patch

import frappe
import json

def install_new_gnr_declarations():
    """Installation des nouveaux DocTypes pour déclarations GNR flexibles"""
    
    print("🚀 Début installation Déclarations GNR flexibles...")
    
    try:
        # 1. Créer les DocTypes enfants
        create_child_doctypes()
        
        # 2. Créer le DocType principal
        create_declaration_periode_gnr()
        
        # 3. Configurer les permissions
        setup_permissions()
        
        # 4. Créer les données de démonstration
        create_demo_data()
        
        print("✅ Installation terminée avec succès !")
        print("📋 Accès via : Menu > GNR Compliance > Declaration Periode GNR")
        
    except Exception as e:
        print(f"❌ Erreur installation : {str(e)}")
        frappe.log_error(f"Erreur installation déclarations GNR : {str(e)}")

def create_child_doctypes():
    """Crée les DocTypes enfants pour les filtres"""
    
    # Type Mouvement Filter
    if not frappe.db.exists("DocType", "Type Mouvement Filter"):
        type_mouvement_filter = {
            "doctype": "DocType",
            "name": "Type Mouvement Filter",
            "module": "GNR Compliance",
            "is_child_table": 1,
            "fields": [
                {
                    "fieldname": "type_mouvement",
                    "fieldtype": "Select",
                    "label": "Type de Mouvement",
                    "options": "Vente\nAchat\nStock\nTransfert\nEntrée\nSortie",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "inclus",
                    "fieldtype": "Check",
                    "label": "Inclure",
                    "default": "1",
                    "in_list_view": 1
                },
                {
                    "fieldname": "description",
                    "fieldtype": "Data",
                    "label": "Description"
                }
            ]
        }
        
        doc = frappe.get_doc(type_mouvement_filter)
        doc.insert(ignore_permissions=True)
        print("✅ DocType 'Type Mouvement Filter' créé")
    
    # Produit GNR Filter
    if not frappe.db.exists("DocType", "Produit GNR Filter"):
        produit_gnr_filter = {
            "doctype": "DocType",
            "name": "Produit GNR Filter",
            "module": "GNR Compliance",
            "is_child_table": 1,
            "fields": [
                {
                    "fieldname": "code_produit",
                    "fieldtype": "Link",
                    "label": "Code Produit",
                    "options": "Item",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "nom_produit",
                    "fieldtype": "Data",
                    "label": "Nom Produit",
                    "read_only": 1,
                    "fetch_from": "code_produit.item_name",
                    "in_list_view": 1
                },
                {
                    "fieldname": "categorie_gnr",
                    "fieldtype": "Data",
                    "label": "Catégorie GNR",
                    "read_only": 1,
                    "fetch_from": "code_produit.gnr_tracked_category"
                },
                {
                    "fieldname": "inclus",
                    "fieldtype": "Check",
                    "label": "Inclure",
                    "default": "1",
                    "in_list_view": 1
                }
            ]
        }
        
        doc = frappe.get_doc(produit_gnr_filter)
        doc.insert(ignore_permissions=True)
        print("✅ DocType 'Produit GNR Filter' créé")

def create_declaration_periode_gnr():
    """Crée le DocType principal Declaration Periode GNR"""
    
    if frappe.db.exists("DocType", "Declaration Periode GNR"):
        print("⚠️ DocType 'Declaration Periode GNR' existe déjà")
        return
    
    declaration_gnr = {
        "doctype": "DocType",
        "name": "Declaration Periode GNR",
        "module": "GNR Compliance",
        "autoname": "format:DECL-{type_periode}-{periode}-{annee}",
        "is_submittable": 1,
        "track_changes": 1,
        "fields": [
            # Section Période
            {
                "fieldname": "section_periode",
                "fieldtype": "Section Break",
                "label": "Période de Déclaration"
            },
            {
                "fieldname": "type_periode",
                "fieldtype": "Select",
                "label": "Type de Période",
                "options": "Mensuel\nTrimestriel\nSemestriel\nAnnuel",
                "reqd": 1,
                "default": "Trimestriel",
                "in_list_view": 1
            },
            {
                "fieldname": "periode",
                "fieldtype": "Data",
                "label": "Période",
                "reqd": 1,
                "in_list_view": 1,
                "description": "Ex: T1, T2, T3, T4 pour trimestriel ou 01, 02... pour mensuel"
            },
            {
                "fieldname": "annee",
                "fieldtype": "Int",
                "label": "Année",
                "reqd": 1,
                "default": "eval:new Date().getFullYear()",
                "in_list_view": 1
            },
            {
                "fieldname": "column_break_periode",
                "fieldtype": "Column Break"
            },
            {
                "fieldname": "date_debut",
                "fieldtype": "Date",
                "label": "Date Début",
                "reqd": 1
            },
            {
                "fieldname": "date_fin",
                "fieldtype": "Date",
                "label": "Date Fin",
                "reqd": 1
            },
            {
                "fieldname": "statut",
                "fieldtype": "Select",
                "label": "Statut",
                "options": "Brouillon\nEn cours\nSoumise\nValidée\nTransmise",
                "default": "Brouillon",
                "in_list_view": 1
            },
            
            # Section Filtres
            {
                "fieldname": "section_filtres",
                "fieldtype": "Section Break",
                "label": "Filtres et Options"
            },
            {
                "fieldname": "types_mouvement",
                "fieldtype": "Table",
                "label": "Types de Mouvement",
                "options": "Type Mouvement Filter",
                "description": "Sélectionner les types de mouvements à inclure"
            },
            {
                "fieldname": "produits_inclus",
                "fieldtype": "Table",
                "label": "Produits Inclus",
                "options": "Produit GNR Filter",
                "description": "Laisser vide pour inclure tous les produits GNR"
            },
            {
                "fieldname": "column_break_filtres",
                "fieldtype": "Column Break"
            },
            {
                "fieldname": "inclure_details_clients",
                "fieldtype": "Check",
                "label": "Inclure Détails Clients",
                "default": "1",
                "description": "Obligatoire pour rapports semestriels"
            },
            {
                "fieldname": "inclure_stocks",
                "fieldtype": "Check",
                "label": "Inclure Mouvements de Stock",
                "default": "1"
            },
            
            # Section Données
            {
                "fieldname": "section_donnees",
                "fieldtype": "Section Break",
                "label": "Données Calculées"
            },
            {
                "fieldname": "stock_debut_periode",
                "fieldtype": "Float",
                "label": "Stock Début (L)",
                "precision": "3",
                "read_only": 1
            },
            {
                "fieldname": "total_entrees",
                "fieldtype": "Float",
                "label": "Total Entrées (L)",
                "precision": "3",
                "read_only": 1
            },
            {
                "fieldname": "total_sorties",
                "fieldtype": "Float",
                "label": "Total Sorties (L)",
                "precision": "3",
                "read_only": 1
            },
            {
                "fieldname": "total_ventes",
                "fieldtype": "Float",
                "label": "Total Ventes (L)",
                "precision": "3",
                "read_only": 1
            },
            {
                "fieldname": "column_break_donnees",
                "fieldtype": "Column Break"
            },
            {
                "fieldname": "stock_fin_periode",
                "fieldtype": "Float",
                "label": "Stock Fin (L)",
                "precision": "3",
                "read_only": 1
            },
            {
                "fieldname": "total_taxe_gnr",
                "fieldtype": "Currency",
                "label": "Total Taxe GNR (€)",
                "read_only": 1
            },
            {
                "fieldname": "nb_clients",
                "fieldtype": "Int",
                "label": "Nombre de Clients",
                "read_only": 1
            },
            
            # Section Observations
            {
                "fieldname": "section_observations",
                "fieldtype": "Section Break",
                "label": "Observations et Données Détaillées"
            },
            {
                "fieldname": "observations",
                "fieldtype": "Text",
                "label": "Observations"
            },
            {
                "fieldname": "donnees_detaillees",
                "fieldtype": "Long Text",
                "label": "Données Détaillées (JSON)",
                "read_only": 1,
                "description": "Stockage des données détaillées au format JSON"
            },
            {
                "fieldname": "amended_from",
                "fieldtype": "Link",
                "label": "Amended From",
                "options": "Declaration Periode GNR",
                "no_copy": 1,
                "print_hide": 1,
                "read_only": 1
            }
        ]
    }
    
    doc = frappe.get_doc(declaration_gnr)
    doc.insert(ignore_permissions=True)
    print("✅ DocType 'Declaration Periode GNR' créé")

def setup_permissions():
    """Configure les permissions pour les nouveaux DocTypes"""
    
    roles = ["System Manager", "GNR Manager"]
    doctypes = ["Declaration Periode GNR", "Type Mouvement Filter", "Produit GNR Filter"]
    
    for doctype in doctypes:
        if frappe.db.exists("DocType", doctype):
            for role in roles:
                if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role}):
                    perm = frappe.get_doc({
                        "doctype": "Custom DocPerm",
                        "parent": doctype,
                        "parenttype": "DocType",
                        "parentfield": "permissions",
                        "role": role,
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                        "submit": 1,
                        "cancel": 1,
                        "amend": 1,
                        "export": 1,
                        "report": 1
                    })
                    perm.insert(ignore_permissions=True)
    
    print("✅ Permissions configurées")

def create_demo_data():
    """Crée des données de démonstration"""
    
    try:
        # Créer une déclaration d'exemple pour T4 2024
        demo_declaration = frappe.get_doc({
            "doctype": "Declaration Periode GNR",
            "type_periode": "Trimestriel",
            "periode": "T4",
            "annee": 2024,
            "date_debut": "2024-10-01",
            "date_fin": "2024-12-31",
            "inclure_details_clients": 1,
            "inclure_stocks": 1,
            "observations": "Déclaration de démonstration - T4 2024"
        })
        
        # Ajouter types de mouvement standard
        for type_mouvement in ["Vente", "Achat", "Entrée", "Sortie"]:
            demo_declaration.append("types_mouvement", {
                "type_mouvement": type_mouvement,
                "inclus": 1,
                "description": f"{type_mouvement} - Configuration standard"
            })
        
        demo_declaration.insert(ignore_permissions=True)
        print(f"✅ Déclaration de démonstration créée : {demo_declaration.name}")
        
    except Exception as e:
        print(f"⚠️ Erreur création données démo : {str(e)}")

# Fonction d'installation principale
def main():
    """Fonction principale d'installation"""
    install_new_gnr_declarations()

# Pour exécution directe dans la console ERPNext
if __name__ == "__main__":
    main()

# Instructions pour ERPNext 15:
"""
INSTALLATION dans ERPNext 15 :

1. Console ERPNext (Préféré) :
   - Aller dans Bench > Developer > Console
   - Copier/coller ce script
   - Exécuter : exec(open('install_declaration_gnr.py').read())

2. Via bench :
   bench execute "gnr_compliance.install.install_declaration_gnr.main"

3. Comme patch dans patches.txt :
   gnr_compliance.install.install_declaration_gnr.main

VÉRIFICATION POST-INSTALLATION :
- Menu > GNR Compliance > Declaration Periode GNR
- Créer une nouvelle déclaration test
- Vérifier les boutons "Charger Produits GNR" et "Types Standard"
- Tester l'export Excel après soumission

MIGRATION DONNÉES :
Si besoin de migrer depuis "Declaration Trimestrielle" :
- Les deux systèmes coexistent
- Migration manuelle recommandée
- Nouveau système pour futures déclarations
"""