# gnr_compliance/integrations/sales.py
import frappe
from frappe.utils import getdate

def capture_vente_gnr(doc, method):
    """Capture automatique des ventes GNR depuis Sales Invoice"""
    # Vérifier si la facture contient des produits GNR
    produits_gnr = []
    for item in doc.items:
        # Vérifier si l'article est soumis à la réglementation GNR
        is_gnr = frappe.get_value("Item", item.item_code, "custom_gnr_applicable")
        if is_gnr:
            produits_gnr.append(item)
    
    if produits_gnr:
        for item in produits_gnr:
            # Créer un mouvement GNR automatiquement
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
                "taux_gnr": frappe.get_value("Item", item.item_code, "custom_taux_gnr") or 0
            })
            mouvement_gnr.insert()
            mouvement_gnr.submit()

def capture_achat_gnr(doc, method):
    """Capture automatique des achats GNR depuis Purchase Invoice"""
    # Logique similaire pour les achats
    produits_gnr = []
    for item in doc.items:
        is_gnr = frappe.get_value("Item", item.item_code, "custom_gnr_applicable")
        if is_gnr:
            mouvement_gnr = frappe.get_doc({
                "doctype": "Mouvement GNR",
                "type_mouvement": "Achat",
                "date_mouvement": doc.posting_date,
                "reference_document": doc.doctype,
                "reference_name": doc.name,
                "code_produit": item.item_code,
                "quantite": item.qty,
                "fournisseur": doc.supplier,
                "taux_gnr": frappe.get_value("Item", item.item_code, "custom_taux_gnr") or 0
            })
            mouvement_gnr.insert()
            mouvement_gnr.submit()