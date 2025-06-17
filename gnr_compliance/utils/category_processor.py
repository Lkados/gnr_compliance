# gnr_app/utils/category_processor.py
import frappe
from frappe import _
import fnmatch
import json

@frappe.whitelist()
def get_gnr_settings():
    """Récupère la configuration GNR avec cache"""
    return frappe.get_cached_doc("GNR Settings")

def validate_item_category(doc, method):
    """Valide et assigne automatiquement les catégories GNR aux articles"""
    try:
        settings = get_gnr_settings()
        
        if not settings.enable_gnr_tracking:
            return
            
        # Vérifier si l'article correspond aux règles de catégories
        matched_category = find_matching_category(doc, settings.category_rules)
        
        if matched_category:
            doc.gnr_tracked_category = matched_category.category_name
            doc.gnr_tracking_enabled = 1
            
            frappe.msgprint(
                _("Article assigné à la catégorie GNR: {0}").format(matched_category.category_name),
                alert=True,
                indicator="green"
            )
        else:
            doc.gnr_tracking_enabled = 0
            
    except Exception as e:
        frappe.log_error(f"Erreur validation catégorie GNR: {str(e)}")

def find_matching_category(doc, category_rules):
    """Trouve la catégorie correspondante selon les règles configurées"""
    matched_categories = []
    
    for rule in category_rules:
        if not rule.is_active:
            continue
            
        matches = True
        
        # Vérifier le pattern du groupe d'articles
        if rule.item_group_pattern:
            if not fnmatch.fnmatch(doc.item_group or "", rule.item_group_pattern):
                matches = False
                
        # Vérifier le pattern du code article
        if rule.item_code_pattern and matches:
            if not fnmatch.fnmatch(doc.item_code or "", rule.item_code_pattern):
                matches = False
                
        # Vérifier le chemin de catégorie dans le nom/groupe
        if rule.category_path and matches:
            path_parts = rule.category_path.split('/')
            item_text = f"{doc.item_name} {doc.item_group}".lower()
            
            if not all(part.lower() in item_text for part in path_parts):
                matches = False
                
        if matches:
            matched_categories.append((rule.priority or 10, rule))
    
    # Retourner la catégorie avec la priorité la plus élevée (valeur la plus faible)
    if matched_categories:
        matched_categories.sort(key=lambda x: x[0])
        return matched_categories[0][1]
    
    return None

def process_category_assignment(doc, method):
    """Traite l'assignation de catégorie avant sauvegarde"""
    try:
        if doc.gnr_tracking_enabled and doc.gnr_tracked_category:
            # Log de l'assignation
            create_category_assignment_log(doc)
            
            # Mettre à jour le cache des articles trackés
            update_tracked_items_cache(doc.item_code, doc.gnr_tracked_category)
            
    except Exception as e:
        frappe.log_error(f"Erreur assignation catégorie: {str(e)}")

def create_category_assignment_log(doc):
    """Crée un log d'assignation de catégorie"""
    try:
        log_entry = frappe.new_doc("GNR Movement Log")
        log_entry.update({
            'reference_doctype': 'Item',
            'reference_name': doc.name,
            'item_code': doc.item_code,
            'gnr_category': doc.gnr_tracked_category,
            'movement_type': 'Category Assignment',
            'user': frappe.session.user,
            'timestamp': frappe.utils.now_datetime(),
            'details': json.dumps({
                'item_name': doc.item_name,
                'item_group': doc.item_group
            })
        })
        log_entry.insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Erreur création log assignation: {str(e)}")

@frappe.whitelist()
def get_tracked_categories():
    """API pour récupérer les catégories trackées actives"""
    settings = get_gnr_settings()
    
    if not settings.enable_gnr_tracking:
        return []
        
    return [
        {
            'name': rule.category_name,
            'path': rule.category_path,
            'priority': rule.priority
        }
        for rule in settings.category_rules
        if rule.is_active
    ]

def update_tracked_items_cache(item_code, category):
    """Met à jour le cache des articles trackés"""
    try:
        cache_key = "gnr_tracked_items"
        tracked_items = frappe.cache().get_value(cache_key) or {}
        
        tracked_items[item_code] = {
            'category': category,
            'updated': frappe.utils.now()
        }
        
        frappe.cache().set_value(cache_key, tracked_items, expires_in_sec=7200)  # 2 heures
        
    except Exception as e:
        frappe.log_error(f"Erreur mise à jour cache: {str(e)}")