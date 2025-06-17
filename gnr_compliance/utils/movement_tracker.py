# gnr_app/utils/movement_tracker.py
import frappe
from frappe import _
from frappe.utils import flt, now_datetime
from frappe import enqueue
import json

def process_stock_movement(doc, method):
    """Traite les mouvements de stock pour les articles GNR"""
    try:
        settings = frappe.get_cached_doc("GNR Settings")
        
        if not settings.enable_gnr_tracking or not settings.auto_capture_movements:
            return
            
        # Traiter chaque article de l'entrée de stock
        gnr_items = []
        
        for item in doc.items:
            if is_gnr_tracked_item(item.item_code):
                gnr_items.append({
                    'item_code': item.item_code,
                    'qty': item.qty,
                    'amount': item.amount,
                    'warehouse': item.t_warehouse or item.s_warehouse,
                    'category': get_item_gnr_category(item.item_code)
                })
        
        if gnr_items:
            # Traitement en arrière-plan pour éviter les ralentissements
            enqueue(
                'gnr_app.utils.movement_tracker.process_gnr_movements',
                queue='default',
                timeout=300,
                stock_entry=doc.name,
                gnr_items=gnr_items,
                movement_type=doc.stock_entry_type
            )
            
            # Marquer comme traité
            frappe.db.set_value("Stock Entry", doc.name, "gnr_category_processed", 1)
            
    except Exception as e:
        frappe.log_error(f"Erreur traitement mouvement stock: {str(e)}")

def process_gnr_movements(stock_entry, gnr_items, movement_type):
    """Traitement en arrière-plan des mouvements GNR"""
    try:
        for item_data in gnr_items:
            # Créer un log de mouvement
            create_movement_log(
                reference_doctype='Stock Entry',
                reference_name=stock_entry,
                item_code=item_data['item_code'],
                category=item_data['category'],
                movement_type=movement_type,
                qty=item_data['qty'],
                amount=item_data['amount'],
                warehouse=item_data['warehouse'],
                details=item_data
            )
            
            # Mettre à jour les statistiques de catégorie
            update_category_statistics(item_data['category'], item_data['qty'], item_data['amount'])
            
        frappe.db.commit()
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Erreur traitement GNR en arrière-plan: {str(e)}")

def create_movement_log(reference_doctype, reference_name, item_code, category, 
                       movement_type, qty=0, amount=0, warehouse=None, details=None):
    """Crée un log de mouvement GNR"""
    try:
        log_entry = frappe.new_doc("GNR Movement Log")
        log_entry.update({
            'reference_doctype': reference_doctype,
            'reference_name': reference_name,
            'item_code': item_code,
            'gnr_category': category,
            'movement_type': movement_type,
            'quantity': flt(qty),
            'amount': flt(amount),
            'warehouse': warehouse,
            'user': frappe.session.user,
            'timestamp': now_datetime(),
            'details': json.dumps(details) if details else None
        })
        log_entry.insert(ignore_permissions=True)
        
        return log_entry.name
        
    except Exception as e:
        frappe.log_error(f"Erreur création log mouvement: {str(e)}")
        return None

def is_gnr_tracked_item(item_code):
    """Vérifie si un article est tracké GNR"""
    try:
        # Vérifier le cache d'abord
        cache_key = "gnr_tracked_items"
        tracked_items = frappe.cache().get_value(cache_key) or {}
        
        if item_code in tracked_items:
            return True
            
        # Vérifier en base de données
        item_doc = frappe.get_cached_doc("Item", item_code)
        return item_doc.get("gnr_tracking_enabled") == 1
        
    except Exception:
        return False

def get_item_gnr_category(item_code):
    """Récupère la catégorie GNR d'un article"""
    try:
        item_doc = frappe.get_cached_doc("Item", item_code)
        return item_doc.get("gnr_tracked_category")
    except Exception:
        return None

def update_category_statistics(category, qty, amount):
    """Met à jour les statistiques de catégorie"""
    try:
        # Récupérer ou créer les stats de catégorie
        stats_key = f"gnr_category_stats_{category}"
        stats = frappe.cache().get_value(stats_key) or {
            'total_qty': 0,
            'total_amount': 0,
            'movement_count': 0,
            'last_updated': now_datetime()
        }
        
        # Mettre à jour
        stats['total_qty'] += flt(qty)
        stats['total_amount'] += flt(amount) 
        stats['movement_count'] += 1
        stats['last_updated'] = now_datetime()
        
        # Sauvegarder dans le cache
        frappe.cache().set_value(stats_key, stats, expires_in_sec=3600)
        
    except Exception as e:
        frappe.log_error(f"Erreur mise à jour statistiques: {str(e)}")

@frappe.whitelist()
def get_category_statistics(category=None):
    """API pour récupérer les statistiques des catégories"""
    try:
        settings = frappe.get_cached_doc("GNR Settings")
        
        if category:
            stats_key = f"gnr_category_stats_{category}"
            return frappe.cache().get_value(stats_key) or {}
        else:
            # Retourner les stats de toutes les catégories actives
            all_stats = {}
            for rule in settings.category_rules:
                if rule.is_active:
                    stats_key = f"gnr_category_stats_{rule.category_name}"
                    all_stats[rule.category_name] = frappe.cache().get_value(stats_key) or {}
            return all_stats
            
    except Exception as e:
        frappe.log_error(f"Erreur récupération statistiques: {str(e)}")
        return {}

def process_pending_movements():
    """Traite les mouvements en attente (tâche planifiée)"""
    try:
        # Rechercher les entrées de stock non traitées avec des articles GNR
        pending_entries = frappe.db.sql("""
            SELECT DISTINCT se.name
            FROM `tabStock Entry` se
            JOIN `tabStock Entry Detail` sed ON se.name = sed.parent
            JOIN `tabItem` i ON sed.item_code = i.item_code
            WHERE se.docstatus = 1
            AND (se.gnr_category_processed IS NULL OR se.gnr_category_processed = 0)
            AND i.gnr_tracking_enabled = 1
            AND se.posting_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            LIMIT 100
        """, as_list=True)
        
        for entry in pending_entries:
            # Retraiter l'entrée
            stock_entry_doc = frappe.get_doc("Stock Entry", entry[0])
            process_stock_movement(stock_entry_doc, "reprocess")
            
        if pending_entries:
            frappe.log_error(f"Retraité {len(pending_entries)} entrées de stock GNR en attente")
            
    except Exception as e:
        frappe.log_error(f"Erreur traitement mouvements en attente: {str(e)}")