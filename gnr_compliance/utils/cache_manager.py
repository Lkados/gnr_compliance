from __future__ import annotations
import frappe
from frappe.utils import now_datetime
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

class GNRCacheManager:
    """Gestionnaire de cache pour les données GNR"""
    
    CACHE_KEYS = {
        'settings': 'gnr_settings',
        'tracked_items': 'gnr_tracked_items',
        'tracked_categories': 'gnr_tracked_categories',
        'category_rules': 'gnr_category_rules',
        'category_stats': 'gnr_category_stats'
    }
    
    DEFAULT_TTL = 3600  # 1 heure
    
    @classmethod
    def get_cache_key(cls, key_type: str, suffix: str = "") -> str:
        """
        Génère une clé de cache
        
        Args:
            key_type: Type de clé
            suffix: Suffixe optionnel
            
        Returns:
            Clé de cache formatée
        """
        base_key = cls.CACHE_KEYS.get(key_type, key_type)
        return f"{base_key}_{suffix}" if suffix else base_key

def refresh_category_cache() -> None:
    """Rafraîchit le cache des catégories GNR (tâche planifiée)"""
    try:
        cache_manager = GNRCacheManager()
        
        # Effacer les caches existants
        for cache_key in cache_manager.CACHE_KEYS.values():
            frappe.cache().delete_value(cache_key)
        
        # Recharger les paramètres en cache
        settings = frappe.get_single("GNR Category Settings")
        
        if settings.enable_category_tracking:
            # Mettre en cache les catégories actives
            active_categories = [
                rule.category_name 
                for rule in settings.category_rules 
                if rule.is_active
            ]
            
            frappe.cache().set_value(
                cache_manager.get_cache_key('tracked_categories'),
                active_categories,
                expires_in_sec=cache_manager.DEFAULT_TTL
            )
            
            # Cache des règles de catégories
            category_rules = [
                {
                    'name': rule.category_name,
                    'path': rule.category_path,
                    'priority': rule.priority,
                    'patterns': {
                        'item_group': rule.item_group_pattern,
                        'item_code': rule.item_code_pattern,
                        'item_name': rule.item_name_pattern,
                        'brand': rule.brand_pattern,
                        'supplier': rule.supplier_pattern
                    },
                    'additional_filters': rule.additional_filters
                }
                for rule in settings.category_rules
                if rule.is_active
            ]
            
            frappe.cache().set_value(
                cache_manager.get_cache_key('category_rules'),
                category_rules,
                expires_in_sec=cache_manager.DEFAULT_TTL
            )
            
            # Mettre à jour le timestamp de dernière mise à jour
            frappe.db.set_value("GNR Category Settings", None, 
                              "last_cache_refresh", now_datetime())
            frappe.db.commit()
            
        logger.info(f"Cache GNR rafraîchi à {now_datetime()}")
        
    except Exception as e:
        logger.error(f"Erreur rafraîchissement cache GNR: {e}")
        frappe.log_error(f"Erreur rafraîchissement cache GNR: {str(e)}")

def get_cached_categories() -> List[str]:
    """
    Récupère les catégories depuis le cache
    
    Returns:
        Liste des noms de catégories actives
    """
    try:
        cache_manager = GNRCacheManager()
        categories = frappe.cache().get_value(cache_manager.get_cache_key('tracked_categories'))
        
        if categories is None:
            # Recharger depuis la base de données si pas en cache
            settings = frappe.get_single("GNR Category Settings")
            if settings.enable_category_tracking:
                categories = [
                    rule.category_name 
                    for rule in settings.category_rules 
                    if rule.is_active
                ]
                frappe.cache().set_value(
                    cache_manager.get_cache_key('tracked_categories'),
                    categories,
                    expires_in_sec=cache_manager.DEFAULT_TTL
                )
            else:
                categories = []
        
        return categories
        
    except Exception as e:
        logger.error(f"Erreur récupération cache catégories: {e}")
        return []

def get_cached_item_status(item_code: str) -> Dict[str, Any]:
    """
    Récupère le statut GNR d'un article depuis le cache
    
    Args:
        item_code: Code de l'article
        
    Returns:
        Dictionnaire avec le statut GNR de l'article
    """
    try:
        cache_manager = GNRCacheManager()
        cache_key = cache_manager.get_cache_key('tracked_items')
        
        tracked_items = frappe.cache().get_value(cache_key) or {}
        
        if item_code not in tracked_items:
            # Charger depuis la base de données
            item_data = frappe.get_value("Item", item_code, 
                                       ["is_gnr_tracked", "gnr_tracked_category", "gnr_tax_rate"],
                                       as_dict=True)
            
            if item_data and item_data.is_gnr_tracked:
                tracked_items[item_code] = {
                    'category': item_data.gnr_tracked_category,
                    'tax_rate': item_data.gnr_tax_rate,
                    'updated': now_datetime()
                }
                
                # Sauvegarder dans le cache
                frappe.cache().set_value(cache_key, tracked_items, 
                                       expires_in_sec=cache_manager.DEFAULT_TTL)
            else:
                return {'is_tracked': False}
        
        return {
            'is_tracked': True,
            'category': tracked_items[item_code].get('category'),
            'tax_rate': tracked_items[item_code].get('tax_rate'),
            'last_updated': tracked_items[item_code].get('updated')
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération statut article {item_code}: {e}")
        return {'is_tracked': False}

def clear_all_gnr_cache() -> None:
    """Efface tout le cache GNR"""
    try:
        cache_manager = GNRCacheManager()
        
        for cache_key in cache_manager.CACHE_KEYS.values():
            frappe.cache().delete_value(cache_key)
            
        # Effacer aussi les caches de statistiques
        for category in get_cached_categories():
            stats_key = cache_manager.get_cache_key('category_stats', category)
            frappe.cache().delete_value(stats_key)
            
        logger.info("Tout le cache GNR effacé")
        
    except Exception as e:
        logger.error(f"Erreur effacement cache GNR: {e}")