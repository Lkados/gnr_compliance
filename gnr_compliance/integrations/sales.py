# Version modifiée de votre fichier existant
import frappe
from frappe.utils import getdate
from gnr_compliance.utils.category_detector import is_gnr_tracked_item

def capture_vente_gnr(doc, method):
    """Capture automatique des ventes GNR depuis Sales Invoice - VERSION AMÉLIORÉE"""
    # Vérifier si la facture contient des produits GNR
    produits_gnr = []
    for item in doc.items:
        # NOUVEAU: Utiliser la détection automatique de catégories
        if is_gnr_tracked_item(item.item_code):
            produits_gnr.append(item)
    
    if produits_gnr:
        for item in produits_gnr:
            # Récupérer la catégorie de l'article
            item_doc = frappe.get_doc("Item", item.item_code)
            
            # Créer un mouvement GNR automatiquement (VOTRE CODE EXISTANT + CATÉGORIE)
            mouvement_gnr = frappe.get_doc({
                "doctype": "Mouvement GNR",
                "type_mouvement": "Vente",
                "date_mouvement": doc.posting_date,
                "reference_document": doc.doctype,
                "reference_name": doc.name,
                "code_produit": item.item_code,
                "designation_produit": item.item_name,
                "quantite": item.qty,
                "prix_unitaire": item.rate,
                "client": doc.customer,
                "code_client": doc.customer,
                "taux_gnr": frappe.get_value("Item", item.item_code, "custom_taux_gnr") or 0,
                # NOUVEAU: Ajouter la catégorie automatiquement détectée
                "categorie_gnr": item_doc.gnr_tracked_category
            })
            mouvement_gnr.insert()
            mouvement_gnr.submit()

def annuler_vente_gnr(doc, method):
    """VOTRE CODE EXISTANT INCHANGÉ"""
    # Votre logique d'annulation existante reste identique
    pass

def capture_achat_gnr(doc, method):
    """Version améliorée de votre capture d'achat existante"""
    produits_gnr = []
    for item in doc.items:
        # NOUVEAU: Utiliser la détection automatique
        if is_gnr_tracked_item(item.item_code):
            item_doc = frappe.get_doc("Item", item.item_code)
            
            mouvement_gnr = frappe.get_doc({
                "doctype": "Mouvement GNR",
                "type_mouvement": "Achat",
                "date_mouvement": doc.posting_date,
                "reference_document": doc.doctype,
                "reference_name": doc.name,
                "code_produit": item.item_code,
                "quantite": item.qty,
                "fournisseur": doc.supplier,
                "taux_gnr": frappe.get_value("Item", item.item_code, "custom_taux_gnr") or 0,
                # NOUVEAU: Catégorie automatique
                "categorie_gnr": item_doc.gnr_tracked_category
            })
            mouvement_gnr.insert()
            mouvement_gnr.submit()