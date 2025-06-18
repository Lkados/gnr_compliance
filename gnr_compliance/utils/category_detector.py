
from __future__ import annotations
import frappe
from frappe import _
import fnmatch
import json
from frappe.utils import now_datetime, flt
from typing import Optional, Dict, List, Any, Tuple
import logging

# Configuration du logger
logger = logging.getLogger(__name__)

class GNRCategoryDetector:
    """Gestionnaire de détection automatique des catégories GNR"""
    
    def __init__(self) -> None:
        self.settings: Optional[Any] = None
        self._load_settings()
    
    def _load_settings(self) -> None:
        """Charge les paramètres GNR avec cache"""
        try:
            self.settings = frappe.get_cached_doc("GNR Category Settings")
        except Exception as e:
            logger.error(f"Erreur chargement paramètres GNR: {e}")
            self.settings = None

def detect_gnr_category(doc: Any, method: str) -> None:
    """
    Détecte automatiquement la catégorie GNR d'un article
    
    Args:
        doc: Document Item
        method: Méthode d'appel (validate, before_insert, etc.)
    """
    try:
        detector = GNRCategoryDetector()
        
        if not detector.settings or not detector.settings.enable_category_tracking:
            return
            
        if not detector.settings.auto_apply_to_new_items and method in ["validate", "before_insert"]:
            return
            
        # Chercher une catégorie correspondante
        matched_category = find_matching_category(doc, detector.settings.category_rules)
        
        if matched_category:
            doc.gnr_tracked_category = matched_category.category_name
            doc.is_gnr_tracked = 1
            doc.gnr_auto_assigned = 1
            doc.gnr_last_updated = now_datetime()
            
            # Récupérer le taux de taxe s'il existe
            tax_rate = frappe.get_value("GNR Tax Rate", 
                                      {"category": matched_category.category_name, "is_active": 1}, 
                                      "rate")
            if tax_rate:
                doc.gnr_tax_rate = flt(tax_rate)
            
            if detector.settings.notification_on_assignment:
                frappe.msgprint(
                    _("Article assigné à la catégorie GNR: {0}").format(matched_category.category_name),
                    alert=True,
                    indicator="green"
                )
        else:
            doc.is_gnr_tracked = 0
            doc.gnr_tracked_category = None
            doc.gnr_auto_assigned = 0
            
    except Exception as e:
        logger.error(f"Erreur détection catégorie GNR pour {doc.name}: {e}")
        frappe.log_error(f"Erreur détection catégorie GNR: {str(e)}")

def find_matching_category(item_doc: Any, category_rules: List[Any]) -> Optional[Any]:
    """
    Trouve la catégorie correspondante selon les règles
    
    Args:
        item_doc: Document Item à analyser
        category_rules: Liste des règles de catégories
        
    Returns:
        Règle de catégorie correspondante ou None
    """
    matched_categories: List[Tuple[int, Any]] = []
    
    for rule in category_rules:
        if not rule.is_active:
            continue
            
        if _rule_matches_item(rule, item_doc):
            matched_categories.append((rule.priority or 10, rule))
    
    # Retourner la catégorie avec la priorité la plus élevée (valeur la plus faible)
    if matched_categories:
        matched_categories.sort(key=lambda x: x[0])
        return matched_categories[0][1]
    
    return None

def _rule_matches_item(rule: Any, item_doc: Any) -> bool:
    """
    Vérifie si une règle correspond à un article
    
    Args:
        rule: Règle de catégorie
        item_doc: Document Item
        
    Returns:
        True si la règle correspond
    """
    # Vérifier le pattern du groupe d'articles
    if rule.item_group_pattern:
        if not fnmatch.fnmatch(item_doc.item_group or "", rule.item_group_pattern):
            return False
            
    # Vérifier le pattern du code article
    if rule.item_code_pattern:
        if not fnmatch.fnmatch(item_doc.item_code or "", rule.item_code_pattern):
            return False
            
    # Vérifier le pattern du nom article
    if rule.item_name_pattern:
        if not fnmatch.fnmatch(item_doc.item_name or "", rule.item_name_pattern):
            return False
            
    # Vérifier le pattern de la marque
    if rule.brand_pattern:
        brand = getattr(item_doc, 'brand', '') or ''
        if not fnmatch.fnmatch(brand, rule.brand_pattern):
            return False
    
    # Vérifier le pattern du fournisseur
    if rule.supplier_pattern:
        # Rechercher le fournisseur principal de l'article
        default_supplier = frappe.get_value("Item Supplier", 
                                          {"parent": item_doc.name, "is_default": 1}, 
                                          "supplier")
        if default_supplier:
            if not fnmatch.fnmatch(default_supplier, rule.supplier_pattern):
                return False
        elif rule.supplier_pattern:  # Si un pattern est défini mais pas de fournisseur
            return False
    
    # Vérifier le chemin de catégorie dans le texte
    if rule.category_path:
        path_parts = rule.category_path.split('/')
        item_text = f"{item_doc.item_name} {item_doc.item_group}".lower()
        
        if not all(part.lower() in item_text for part in path_parts):
            return False
            
    # Vérifier les filtres additionnels JSON
    if rule.additional_filters:
        try:
            additional_conditions = json.loads(rule.additional_filters)
            for field, expected_value in additional_conditions.items():
                if hasattr(item_doc, field):
                    actual_value = getattr(item_doc, field)
                    if actual_value != expected_value:
                        return False
        except json.JSONDecodeError:
            logger.warning(f"Filtres JSON mal formés pour la règle {rule.category_name}")
            
    return True

def log_category_assignment(doc: Any, method: str) -> None:
    """
    Log l'assignation de catégorie
    
    Args:
        doc: Document Item
        method: Méthode d'appel
    """
    if doc.is_gnr_tracked and doc.gnr_tracked_category:
        create_category_log(doc)
        update_statistics()

def create_category_log(doc: Any) -> None:
    """
    Crée un log d'assignation dans le système
    
    Args:
        doc: Document Item
    """
    try:
        log_entry = frappe.new_doc("GNR Movement Log")
        log_entry.update({
            'reference_doctype': 'Item',
            'reference_name': doc.name,
            'item_code': doc.item_code,
            'gnr_category': doc.gnr_tracked_category,
            'movement_type': 'Category Assignment',
            'quantity': 0,
            'amount': 0,
            'user': frappe.session.user,
            'timestamp': now_datetime(),
            'details': json.dumps({
                'item_name': doc.item_name,
                'item_group': doc.item_group,
                'auto_assigned': doc.gnr_auto_assigned
            })
        })
        log_entry.insert(ignore_permissions=True)
        
    except Exception as e:
        logger.error(f"Erreur création log catégorie pour {doc.name}: {e}")

@frappe.whitelist()
def apply_categories_to_existing_items() -> Dict[str, int]:
    """
    Applique les catégories aux articles existants
    
    Returns:
        Dictionnaire avec le nombre d'articles mis à jour
    """
    try:
        settings = frappe.get_single("GNR Category Settings")
        
        if not settings.enable_category_tracking:
            return {'updated_count': 0}
        
        # Récupérer tous les articles non trackés
        items = frappe.get_all("Item", 
                              filters={"disabled": 0, "is_gnr_tracked": 0},
                              fields=["name", "item_code", "item_name", "item_group"])
        
        updated_count = 0
        batch_size = 50
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            for item in batch:
                item_doc = frappe.get_doc("Item", item.name)
                matched_category = find_matching_category(item_doc, settings.category_rules)
                
                if matched_category:
                    frappe.db.set_value("Item", item.name, {
                        "gnr_tracked_category": matched_category.category_name,
                        "is_gnr_tracked": 1,
                        "gnr_auto_assigned": 1,
                        "gnr_last_updated": now_datetime()
                    })
                    updated_count += 1
            
            # Commit par lot pour éviter les timeouts
            frappe.db.commit()
        
        # Mettre à jour les statistiques
        update_statistics()
        
        return {'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Erreur application catégories existantes: {e}")
        frappe.throw(_("Erreur lors de l'application des catégories: {0}").format(str(e)))

def update_statistics() -> None:
    """Met à jour les statistiques dans GNR Category Settings"""
    try:
        total_tracked = frappe.db.count("Item", {"is_gnr_tracked": 1})
        
        frappe.db.set_value("GNR Category Settings", None, {
            "total_tracked_items": total_tracked,
            "last_cache_refresh": now_datetime()
        })
        
    except Exception as e:
        logger.error(f"Erreur mise à jour statistiques: {e}")

@frappe.whitelist()
def get_tracked_categories_summary() -> List[Dict[str, Any]]:
    """
    Récupère un résumé des catégories trackées
    
    Returns:
        Liste des catégories avec leurs statistiques
    """
    try:
        result = frappe.db.sql("""
            SELECT 
                gnr_tracked_category as category,
                COUNT(*) as item_count,
                SUM(CASE WHEN gnr_auto_assigned = 1 THEN 1 ELSE 0 END) as auto_assigned_count
            FROM `tabItem`
            WHERE is_gnr_tracked = 1 
            AND gnr_tracked_category IS NOT NULL
            AND disabled = 0
            GROUP BY gnr_tracked_category
            ORDER BY item_count DESC
        """, as_dict=True)
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur récupération résumé: {e}")
        return []

def is_gnr_tracked_item(item_code: str) -> bool:
    """
    Vérifie si un article est tracké GNR
    
    Args:
        item_code: Code de l'article
        
    Returns:
        True si l'article est tracké GNR
    """
    try:
        return frappe.get_value("Item", item_code, "is_gnr_tracked") == 1
    except Exception:
        return False

def process_pending_categorization() -> None:
    """Traite les articles en attente de catégorisation (tâche planifiée)"""
    try:
        # Rechercher les articles sans catégorie
        uncategorized_items = frappe.get_all("Item",
            filters={
                "disabled": 0,
                "is_gnr_tracked": 0
            },
            fields=["name"],
            limit=100  # Traiter par lots
        )
        
        settings = frappe.get_single("GNR Category Settings")
        
        if not settings.enable_category_tracking:
            return
        
        processed_count = 0
        
        for item in uncategorized_items:
            item_doc = frappe.get_doc("Item", item.name)
            matched_category = find_matching_category(item_doc, settings.category_rules)
            
            if matched_category:
                frappe.db.set_value("Item", item.name, {
                    "gnr_tracked_category": matched_category.category_name,
                    "is_gnr_tracked": 1,
                    "gnr_auto_assigned": 1,
                    "gnr_last_updated": now_datetime()
                })
                processed_count += 1
        
        if processed_count > 0:
            frappe.db.commit()
            update_statistics()
            logger.info(f"Traitement automatique: {processed_count} articles catégorisés")
            
    except Exception as e:
        logger.error(f"Erreur traitement catégorisation en attente: {e}")