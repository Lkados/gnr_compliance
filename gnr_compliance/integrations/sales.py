
from __future__ import annotations
import frappe
from frappe.utils import flt, now_datetime
from gnr_compliance.utils.category_detector import is_gnr_tracked_item
from gnr_compliance.utils.cache_manager import get_cached_item_status
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def capture_vente_gnr(doc: Any, method: str) -> None:
    """
    Capture automatique des ventes GNR depuis Sales Invoice
    
    Args:
        doc: Document Sales Invoice
        method: Méthode d'appel
    """
    try:
        produits_gnr = []
        
        for item in doc.items:
            if is_gnr_tracked_item(item.item_code):
                produits_gnr.append(item)
        
        if produits_gnr:
            for item in produits_gnr:
                _create_gnr_sale_movement(doc, item)
                
            logger.info(f"Vente GNR capturée: {len(produits_gnr)} articles dans {doc.name}")
            
    except Exception as e:
        logger.error(f"Erreur capture vente GNR {doc.name}: {e}")
        frappe.log_error(f"Erreur capture vente GNR: {str(e)}")

def _create_gnr_sale_movement(invoice_doc: Any, item: Any) -> None:
    """
    Crée un mouvement GNR pour une vente
    
    Args:
        invoice_doc: Document Sales Invoice
        item: Ligne d'article de la facture
    """
    try:
        # Récupérer les données GNR de l'article
        item_status = get_cached_item_status(item.item_code)
        
        if not item_status.get('is_tracked'):
            return
            
        # Créer un log de mouvement
        log_entry = frappe.new_doc("GNR Movement Log")
        log_entry.update({
            'reference_doctype': 'Sales Invoice',
            'reference_name': invoice_doc.name,
            'item_code': item.item_code,
            'gnr_category': item_status.get('category'),
            'movement_type': 'Sale',
            'quantity': flt(item.qty),
            'amount': flt(item.amount),
            'user': frappe.session.user,
            'timestamp': now_datetime(),
            'details': json.dumps({
                'customer': invoice_doc.customer,
                'customer_name': invoice_doc.customer_name,
                'rate': item.rate,
                'warehouse': item.warehouse
            })
        })
        log_entry.insert(ignore_permissions=True)
        
        # Créer un mouvement GNR si le DocType existe
        if frappe.db.exists("DocType", "Mouvement GNR"):
            mouvement_gnr = frappe.new_doc("Mouvement GNR")
            mouvement_gnr.update({
                "type_mouvement": "Vente",
                "date_mouvement": invoice_doc.posting_date,
                "reference_document": invoice_doc.doctype,
                "reference_name": invoice_doc.name,
                "code_produit": item.item_code,
                "designation_produit": item.item_name,
                "quantite": flt(item.qty),
                "prix_unitaire": flt(item.rate),
                "client": invoice_doc.customer,
                "code_client": invoice_doc.customer,
                "taux_gnr": flt(item_status.get('tax_rate', 0)),
                "categorie_gnr": item_status.get('category')
            })
            
            # Calculer les taxes
            if mouvement_gnr.quantite and mouvement_gnr.taux_gnr:
                mouvement_gnr.montant_taxe_gnr = mouvement_gnr.quantite * mouvement_gnr.taux_gnr
            
            mouvement_gnr.insert(ignore_permissions=True)
            mouvement_gnr.submit()
            
    except Exception as e:
        logger.error(f"Erreur création mouvement vente GNR pour {item.item_code}: {e}")

def capture_achat_gnr(doc: Any, method: str) -> None:
    """
    Capture automatique des achats GNR depuis Purchase Invoice
    
    Args:
        doc: Document Purchase Invoice
        method: Méthode d'appel
    """
    try:
        produits_gnr = []
        
        for item in doc.items:
            if is_gnr_tracked_item(item.item_code):
                produits_gnr.append(item)
        
        if produits_gnr:
            for item in produits_gnr:
                _create_gnr_purchase_movement(doc, item)
                
            logger.info(f"Achat GNR capturé: {len(produits_gnr)} articles dans {doc.name}")
            
    except Exception as e:
        logger.error(f"Erreur capture achat GNR {doc.name}: {e}")

def _create_gnr_purchase_movement(invoice_doc: Any, item: Any) -> None:
    """
    Crée un mouvement GNR pour un achat
    
    Args:
        invoice_doc: Document Purchase Invoice
        item: Ligne d'article de la facture
    """
    try:
        item_status = get_cached_item_status(item.item_code)
        
        if not item_status.get('is_tracked'):
            return
            
        # Créer un log de mouvement
        log_entry = frappe.new_doc("GNR Movement Log")
        log_entry.update({
            'reference_doctype': 'Purchase Invoice',
            'reference_name': invoice_doc.name,
            'item_code': item.item_code,
            'gnr_category': item_status.get('category'),
            'movement_type': 'Purchase',
            'quantity': flt(item.qty),
            'amount': flt(item.amount),
            'user': frappe.session.user,
            'timestamp': now_datetime(),
            'details': json.dumps({
                'supplier': invoice_doc.supplier,
                'supplier_name': invoice_doc.supplier_name,
                'rate': item.rate,
                'warehouse': item.warehouse
            })
        })
        log_entry.insert(ignore_permissions=True)
        
        # Créer un mouvement GNR si nécessaire
        if frappe.db.exists("DocType", "Mouvement GNR"):
            mouvement_gnr = frappe.new_doc("Mouvement GNR")
            mouvement_gnr.update({
                "type_mouvement": "Achat",
                "date_mouvement": invoice_doc.posting_date,
                "reference_document": invoice_doc.doctype,
                "reference_name": invoice_doc.name,
                "code_produit": item.item_code,
                "designation_produit": item.item_name,
                "quantite": flt(item.qty),
                "prix_unitaire": flt(item.rate),
                "fournisseur": invoice_doc.supplier,
                "taux_gnr": flt(item_status.get('tax_rate', 0)),
                "categorie_gnr": item_status.get('category')
            })
            
            mouvement_gnr.insert(ignore_permissions=True)
            mouvement_gnr.submit()
            
    except Exception as e:
        logger.error(f"Erreur création mouvement achat GNR pour {item.item_code}: {e}")

def annuler_vente_gnr(doc: Any, method: str) -> None:
    """Annule les mouvements GNR d'une vente annulée"""
    _annuler_mouvements_gnr(doc, "Sales Invoice")

def annuler_achat_gnr(doc: Any, method: str) -> None:
    """Annule les mouvements GNR d'un achat annulé"""
    _annuler_mouvements_gnr(doc, "Purchase Invoice")

def _annuler_mouvements_gnr(doc: Any, doctype: str) -> None:
    """
    Annule les mouvements GNR associés à un document annulé
    
    Args:
        doc: Document annulé
        doctype: Type de document
    """
    try:
        # Annuler les logs
        logs = frappe.get_all("GNR Movement Log",
                             filters={
                                 "reference_doctype": doctype,
                                 "reference_name": doc.name
                             })
        
        for log in logs:
            frappe.delete_doc("GNR Movement Log", log.name, ignore_permissions=True)
        
        # Annuler les mouvements GNR
        if frappe.db.exists("DocType", "Mouvement GNR"):
            mouvements = frappe.get_all("Mouvement GNR",
                                       filters={
                                           "reference_document": doctype,
                                           "reference_name": doc.name,
                                           "docstatus": 1
                                       })
            
            for mouvement in mouvements:
                mouvement_doc = frappe.get_doc("Mouvement GNR", mouvement.name)
                mouvement_doc.cancel()
        
        logger.info(f"Mouvements GNR annulés pour {doctype} {doc.name}")
        
    except Exception as e:
        logger.error(f"Erreur annulation mouvements GNR pour {doc.name}: {e}")