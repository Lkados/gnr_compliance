from __future__ import annotations
import frappe
from frappe.utils import flt, now_datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

def capture_mouvement_stock(doc: Any, method: str) -> None:
    """
    Capture des mouvements de stock pour produits GNR
    
    Args:
        doc: Document Stock Entry
        method: Méthode d'appel (on_submit, on_cancel)
    """
    try:
        if doc.stock_entry_type not in ["Material Receipt", "Material Issue", "Material Transfer"]:
            return
            
        gnr_items = []
        gnr_count = 0
        
        for item in doc.items:
            # CORRECTION: Utiliser le bon nom de champ
            if frappe.get_value("Item", item.item_code, "is_gnr_tracked"):
                gnr_items.append(item)
                gnr_count += 1
        
        if gnr_items:
            # Mettre à jour le compteur d'articles GNR détectés
            frappe.db.set_value("Stock Entry", doc.name, "gnr_items_detected", gnr_count)
            
            # Traiter chaque article GNR
            for item in gnr_items:
                _create_gnr_movement_from_stock(doc, item)
            
            # Marquer comme traité
            frappe.db.set_value("Stock Entry", doc.name, "gnr_categories_processed", 1)
            frappe.db.commit()
            
            logger.info(f"Traitement GNR: {len(gnr_items)} articles dans {doc.name}")
            
    except Exception as e:
        logger.error(f"Erreur traitement mouvement stock {doc.name}: {e}")
        frappe.log_error(f"Erreur traitement mouvement stock: {str(e)}")

def _create_gnr_movement_from_stock(stock_doc: Any, item: Any) -> None:
    """
    Crée un mouvement GNR depuis un mouvement de stock
    
    Args:
        stock_doc: Document Stock Entry
        item: Ligne d'article du mouvement de stock
    """
    try:
        # Récupérer les données GNR de l'article
        item_gnr_data = frappe.get_value("Item", item.item_code,
                                       ["gnr_tracked_category", "gnr_tax_rate"],
                                       as_dict=True)
        
        if not item_gnr_data:
            return
            
        # Déterminer le type de mouvement
        movement_type_map = {
            "Material Receipt": "Entrée",
            "Material Issue": "Sortie",
            "Material Transfer": "Transfert"
        }
        
        # Créer un log de mouvement GNR
        log_entry = frappe.new_doc("GNR Movement Log")
        log_entry.update({
            'reference_doctype': 'Stock Entry',
            'reference_name': stock_doc.name,
            'item_code': item.item_code,
            'gnr_category': item_gnr_data.gnr_tracked_category,
            'movement_type': 'Stock Movement',
            'quantity': flt(item.qty),
            'amount': flt(item.amount or 0),
            'warehouse': item.t_warehouse or item.s_warehouse,
            'user': frappe.session.user,
            'timestamp': now_datetime(),
            'details': json.dumps({
                'stock_entry_type': stock_doc.stock_entry_type,
                'movement_type': movement_type_map.get(stock_doc.stock_entry_type),
                's_warehouse': item.s_warehouse,
                't_warehouse': item.t_warehouse,
                'basic_rate': item.basic_rate
            })
        })
        log_entry.insert(ignore_permissions=True)
        
        # Si c'est un mouvement nécessitant la création d'un Mouvement GNR
        if frappe.db.exists("DocType", "Mouvement GNR"):
            mouvement_gnr = frappe.new_doc("Mouvement GNR")
            mouvement_gnr.update({
                "type_mouvement": movement_type_map.get(stock_doc.stock_entry_type, "Mouvement"),
                "date_mouvement": stock_doc.posting_date,
                "reference_document": stock_doc.doctype,
                "reference_name": stock_doc.name,
                "code_produit": item.item_code,
                "designation_produit": item.item_name or frappe.get_value("Item", item.item_code, "item_name"),
                "quantite": flt(item.qty),
                "entrepot_source": item.s_warehouse,
                "entrepot_destination": item.t_warehouse,
                "taux_gnr": flt(item_gnr_data.gnr_tax_rate or 0),
                "categorie_gnr": item_gnr_data.gnr_tracked_category
            })
            mouvement_gnr.insert(ignore_permissions=True)
            if stock_doc.docstatus == 1:
                mouvement_gnr.submit()
        
    except Exception as e:
        logger.error(f"Erreur création mouvement GNR pour {item.item_code}: {e}")

def annuler_mouvement_stock(doc: Any, method: str) -> None:
    """
    Annule les mouvements GNR associés à un mouvement de stock annulé
    
    Args:
        doc: Document Stock Entry
        method: Méthode d'appel
    """
    try:
        # Annuler les logs de mouvement associés
        logs = frappe.get_all("GNR Movement Log",
                             filters={
                                 "reference_doctype": "Stock Entry",
                                 "reference_name": doc.name
                             })
        
        for log in logs:
            frappe.delete_doc("GNR Movement Log", log.name, ignore_permissions=True)
        
        # Annuler les mouvements GNR associés
        if frappe.db.exists("DocType", "Mouvement GNR"):
            mouvements = frappe.get_all("Mouvement GNR",
                                       filters={
                                           "reference_document": "Stock Entry",
                                           "reference_name": doc.name,
                                           "docstatus": 1
                                       })
            
            for mouvement in mouvements:
                mouvement_doc = frappe.get_doc("Mouvement GNR", mouvement.name)
                if mouvement_doc.docstatus == 1:
                    mouvement_doc.cancel()
        
        logger.info(f"Mouvements GNR annulés pour {doc.name}")
        
    except Exception as e:
        logger.error(f"Erreur annulation mouvements GNR pour {doc.name}: {e}")
