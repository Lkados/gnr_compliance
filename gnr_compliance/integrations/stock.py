# gnr_compliance/integrations/stock.py - VERSION CORRIGÉE
from __future__ import annotations
import frappe
from frappe.utils import flt, now_datetime, getdate  # SUPPRIMÉ get_quarter
from typing import Dict, List, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)

def get_quarter_from_date(date_obj):
    """Calcule le trimestre à partir d'une date"""
    if isinstance(date_obj, str):
        date_obj = getdate(date_obj)
    return str((date_obj.month - 1) // 3 + 1)

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
            # Vérifier si l'article est tracké GNR
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
        
        # Convertir la date de posting en objet date
        posting_date = getdate(stock_doc.posting_date)
        
        # Créer un log de mouvement GNR
        try:
            log_entry = frappe.new_doc("GNR Movement Log")
            log_entry.update({
                'reference_doctype': 'Stock Entry',
                'reference_name': stock_doc.name,
                'item_code': item.item_code,
                'gnr_category': item_gnr_data.gnr_tracked_category,
                'movement_type': 'Stock Movement',
                'quantity': flt(item.qty),
                'amount': flt(item.amount or 0),
                'user': frappe.session.user,
                'timestamp': now_datetime()
            })
            log_entry.insert(ignore_permissions=True)
        except Exception as log_error:
            # Si GNR Movement Log n'existe pas, ignorer
            logger.info(f"GNR Movement Log non disponible: {log_error}")
        
        # Si c'est un mouvement nécessitant la création d'un Mouvement GNR
        if frappe.db.exists("DocType", "Mouvement GNR"):
            mouvement_gnr = frappe.new_doc("Mouvement GNR")
            mouvement_gnr.update({
                "type_mouvement": movement_type_map.get(stock_doc.stock_entry_type, "Stock"),
                "date_mouvement": posting_date,
                "reference_document": stock_doc.doctype,
                "reference_name": stock_doc.name,
                "code_produit": item.item_code,
                "quantite": flt(item.qty),
                "prix_unitaire": flt(item.basic_rate or 0),
                "taux_gnr": flt(item_gnr_data.gnr_tax_rate or 0),
                "categorie_gnr": item_gnr_data.gnr_tracked_category,
                "trimestre": get_quarter_from_date(posting_date),  # FONCTION CORRIGÉE
                "annee": posting_date.year,
                "semestre": "1" if posting_date.month <= 6 else "2"
            })
            
            # Calculer le montant de taxe GNR
            if mouvement_gnr.quantite and mouvement_gnr.taux_gnr:
                mouvement_gnr.montant_taxe_gnr = mouvement_gnr.quantite * mouvement_gnr.taux_gnr
            
            mouvement_gnr.insert(ignore_permissions=True)
            
            if stock_doc.docstatus == 1:
                mouvement_gnr.submit()
        
    except Exception as e:
        logger.error(f"Erreur création mouvement GNR pour {item.item_code}: {e}")

def cancel_mouvement_stock(doc: Any, method: str) -> None:
    """
    Annule les mouvements GNR associés à un mouvement de stock annulé
    
    Args:
        doc: Document Stock Entry
        method: Méthode d'appel
    """
    try:
        # Annuler les logs de mouvement associés (si ils existent)
        try:
            logs = frappe.get_all("GNR Movement Log",
                                 filters={
                                     "reference_doctype": "Stock Entry",
                                     "reference_name": doc.name
                                 })
            
            for log in logs:
                frappe.delete_doc("GNR Movement Log", log.name, ignore_permissions=True)
        except Exception as log_error:
            # Si GNR Movement Log n'existe pas, ignorer
            logger.info(f"GNR Movement Log non disponible pour annulation: {log_error}")
        
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

@frappe.whitelist()
def get_stock_gnr_summary(from_date: str, to_date: str) -> Dict[str, Any]:
    """
    Récupère un résumé des mouvements de stock GNR sur une période
    
    Args:
        from_date: Date de début
        to_date: Date de fin
        
    Returns:
        Dictionnaire avec le résumé des mouvements
    """
    try:
        # Convertir les dates
        from_date_obj = getdate(from_date)
        to_date_obj = getdate(to_date)
        
        # Requête pour récupérer les mouvements de stock GNR
        movements = frappe.db.sql("""
            SELECT 
                m.categorie_gnr as gnr_category,
                m.type_mouvement as movement_type,
                COUNT(*) as count,
                SUM(m.quantite) as total_quantity,
                SUM(COALESCE(m.quantite * m.prix_unitaire, 0)) as total_amount
            FROM `tabMouvement GNR` m
            WHERE m.reference_document = 'Stock Entry'
            AND m.date_mouvement BETWEEN %s AND %s
            AND m.docstatus = 1
            GROUP BY m.categorie_gnr, m.type_mouvement
            ORDER BY m.categorie_gnr, m.type_mouvement
        """, (from_date_obj, to_date_obj), as_dict=True)
        
        # Organiser les données par catégorie
        summary = {}
        for movement in movements:
            category = movement.gnr_category or "Non classé"
            if category not in summary:
                summary[category] = {
                    'total_movements': 0,
                    'total_quantity': 0,
                    'total_amount': 0,
                    'by_type': {}
                }
            
            summary[category]['total_movements'] += movement.count
            summary[category]['total_quantity'] += movement.total_quantity or 0
            summary[category]['total_amount'] += movement.total_amount or 0
            summary[category]['by_type'][movement.movement_type] = {
                'count': movement.count,
                'quantity': movement.total_quantity or 0,
                'amount': movement.total_amount or 0
            }
        
        return {
            'success': True,
            'from_date': from_date,
            'to_date': to_date,
            'categories': summary,
            'total_categories': len(summary)
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération résumé stock GNR: {e}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def reprocess_stock_entry(stock_entry_name: str) -> Dict[str, Any]:
    """
    Retraite un mouvement de stock pour les articles GNR
    
    Args:
        stock_entry_name: Nom du mouvement de stock
        
    Returns:
        Résultat du retraitement
    """
    try:
        stock_doc = frappe.get_doc("Stock Entry", stock_entry_name)
        
        if stock_doc.docstatus != 1:
            return {'success': False, 'message': 'Le mouvement de stock doit être validé'}
        
        # Supprimer les anciens logs
        cancel_mouvement_stock(stock_doc, "reprocess")
        
        # Recreer les mouvements
        capture_mouvement_stock(stock_doc, "reprocess")
        
        return {
            'success': True,
            'message': f'Mouvement de stock {stock_entry_name} retraité avec succès'
        }
        
    except Exception as e:
        logger.error(f"Erreur retraitement {stock_entry_name}: {e}")
        return {'success': False, 'error': str(e)}