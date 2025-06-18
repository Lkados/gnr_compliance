import frappe
from frappe.utils import now_datetime

def refresh_category_cache():
    """Rafraîchit le cache des catégories GNR (tâche planifiée)"""
    try:
        # Effacer les caches existants
        frappe.cache().delete_value("gnr_settings")
        frappe.cache().delete_value("gnr_tracked_items")
        frappe.cache().delete_value("gnr_tracked_categories")
        
        # Recharger les paramètres en cache
        settings = frappe.get_single("GNR Category Settings")
        
        if settings.enable_category_tracking:
            # Mettre en cache les catégories actives
            active_categories = [
                rule.category_name 
                for rule in settings.category_rules 
                if rule.is_active
            ]
            
            frappe.cache().set_value("gnr_tracked_categories", active_categories, expires_in_sec=3600)
            
            # Mettre à jour le timestamp de dernière mise à jour
            frappe.db.set_value("GNR Category Settings", None, "last_cache_refresh", now_datetime())
            frappe.db.commit()
            
        print(f"✅ Cache GNR rafraîchi à {now_datetime()}")
        
    except Exception as e:
        frappe.log_error(f"Erreur rafraîchissement cache GNR: {str(e)}")

def get_cached_categories():
    """Récupère les catégories depuis le cache"""
    try:
        categories = frappe.cache().get_value("gnr_tracked_categories")
        
        if categories is None:
            # Recharger depuis la base de données si pas en cache
            settings = frappe.get_single("GNR Category Settings")
            if settings.enable_category_tracking:
                categories = [
                    rule.category_name 
                    for rule in settings.category_rules 
                    if rule.is_active
                ]
                frappe.cache().set_value("gnr_tracked_categories", categories, expires_in_sec=3600)
            else:
                categories = []
        
        return categories
        
    except Exception as e:
        frappe.log_error(f"Erreur récupération cache catégories: {str(e)}")
        return []

def clear_all_gnr_cache():
    """Efface tout le cache GNR"""
    try:
        cache_keys = [
            "gnr_settings",
            "gnr_tracked_items", 
            "gnr_tracked_categories",
            "gnr_category_rules"
        ]
        
        for key in cache_keys:
            frappe.cache().delete_value(key)
            
        print("✅ Tout le cache GNR effacé")
        
    except Exception as e:
        frappe.log_error(f"Erreur effacement cache GNR: {str(e)}")