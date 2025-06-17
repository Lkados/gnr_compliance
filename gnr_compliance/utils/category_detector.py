import frappe
from frappe import _
import fnmatch
import json
from frappe.utils import now_datetime

def detect_gnr_category(doc, method):
    """Détecte automatiquement la catégorie GNR d'un article"""
    try:
        settings = frappe.get_single("GNR Category Settings")
        
        if not settings.enable_category_tracking or not settings.auto_apply_to_new_items:
            return
            
        # Chercher une catégorie correspondante
        matched_category = find_matching_category(doc, settings.category_rules)
        
        if matched_category:
            doc.gnr_tracked_category = matched_category.category_name
            doc.is_gnr_tracked = 1
            
            if settings.notification_on_assignment:
                frappe.msgprint(
                    _("Article assigné à la catégorie GNR: {0}").format(matched_category.category_name),
                    alert=True,
                    indicator="green"
                )
        else:
            doc.is_gnr_tracked = 0
            
    except Exception as e:
        frappe.log_error(f"Erreur détection catégorie GNR: {str(e)}")

def find_matching_category(item_doc, category_rules):
    """Trouve la catégorie correspondante selon les règles"""
    matched_categories = []
    
    for rule in category_rules:
        if not rule.is_active:
            continue
            
        matches = True
        
        # Vérifier le pattern du groupe d'articles
        if rule.item_group_pattern:
            if not fnmatch.fnmatch(item_doc.item_group or "", rule.item_group_pattern):
                matches = False
                
        # Vérifier le pattern du code article
        if rule.item_code_pattern and matches:
            if not fnmatch.fnmatch(item_doc.item_code or "", rule.item_code_pattern):
                matches = False
                
        # Vérifier le pattern du nom article
        if rule.item_name_pattern and matches:
            if not fnmatch.fnmatch(item_doc.item_name or "", rule.item_name_pattern):
                matches = False
                
        # Vérifier le pattern de la marque
        if rule.brand_pattern and matches:
            brand = getattr(item_doc, 'brand', '') or ''
            if not fnmatch.fnmatch(brand, rule.brand_pattern):
                matches = False
        
        # Vérifier le chemin de catégorie dans le texte
        if rule.category_path and matches:
            path_parts = rule.category_path.split('/')
            item_text = f"{item_doc.item_name} {item_doc.item_group}".lower()
            
            if not all(part.lower() in item_text for part in path_parts):
                matches = False
                
        # Vérifier les filtres additionnels JSON
        if rule.additional_filters and matches:
            try:
                additional_conditions = json.loads(rule.additional_filters)
                for field, expected_value in additional_conditions.items():
                    if hasattr(item_doc, field):
                        actual_value = getattr(item_doc, field)
                        if actual_value != expected_value:
                            matches = False
                            break
            except json.JSONDecodeError:
                pass  # Ignorer les filtres mal formés
                
        if matches:
            matched_categories.append((rule.priority or 10, rule))
    
    # Retourner la catégorie avec la priorité la plus élevée (valeur la plus faible)
    if matched_categories:
        matched_categories.sort(key=lambda x: x[0])
        return matched_categories[0][1]
    
    return None

def log_category_assignment(doc, method):
    """Log l'assignation de catégorie"""
    if doc.is_gnr_tracked and doc.gnr_tracked_category:
        create_category_log(doc)
        update_statistics()

def create_category_log(doc):
    """Crée un log d'assignation dans le système existant"""
    try:
        # Utiliser votre DocType "Mouvement GNR" existant pour log
        mouvement = frappe.new_doc("Mouvement GNR")
        mouvement.update({
            'type_mouvement': 'Assignation Catégorie',
            'date_mouvement': frappe.utils.today(),
            'code_produit': doc.item_code,
            'designation_produit': doc.item_name,
            'reference_document': 'Item',
            'reference_name': doc.name,
            'quantite': 0,
            'commentaire': f"Article assigné à la catégorie: {doc.gnr_tracked_category}"
        })
        mouvement.insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Erreur création log catégorie: {str(e)}")

@frappe.whitelist()
def apply_categories_to_existing_items():
    """Applique les catégories aux articles existants"""
    settings = frappe.get_single("GNR Category Settings")
    
    if not settings.enable_category_tracking:
        return {'updated_count': 0}
    
    # Récupérer tous les articles
    items = frappe.get_all("Item", 
                          filters={"disabled": 0},
                          fields=["name", "item_code", "item_name", "item_group"])
    
    updated_count = 0
    
    for item in items:
        item_doc = frappe.get_doc("Item", item.name)
        matched_category = find_matching_category(item_doc, settings.category_rules)
        
        if matched_category:
            frappe.db.set_value("Item", item.name, {
                "gnr_tracked_category": matched_category.category_name,
                "is_gnr_tracked": 1
            })
            updated_count += 1
    
    # Mettre à jour les statistiques
    update_statistics()
    
    frappe.db.commit()
    return {'updated_count': updated_count}

def update_statistics():
    """Met à jour les statistiques dans GNR Category Settings"""
    try:
        total_tracked = frappe.db.count("Item", {"is_gnr_tracked": 1})
        
        frappe.db.set_value("GNR Category Settings", None, {
            "total_tracked_items": total_tracked,
            "last_cache_refresh": now_datetime()
        })
        
    except Exception as e:
        frappe.log_error(f"Erreur mise à jour statistiques: {str(e)}")

@frappe.whitelist()
def get_tracked_categories_summary():
    """Récupère un résumé des catégories trackées"""
    try:
        result = frappe.db.sql("""
            SELECT 
                gnr_tracked_category as category,
                COUNT(*) as item_count
            FROM `tabItem`
            WHERE is_gnr_tracked = 1 
            AND gnr_tracked_category IS NOT NULL
            GROUP BY gnr_tracked_category
            ORDER BY item_count DESC
        """, as_dict=True)
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Erreur récupération résumé: {str(e)}")
        return []

def is_gnr_tracked_item(item_code):
    """Vérifie si un article est tracké GNR"""
    try:
        return frappe.get_value("Item", item_code, "is_gnr_tracked") == 1
    except Exception:
        return False

def process_pending_categorization():
    """Traite les articles en attente de catégorisation (tâche planifiée)"""
    try:
        # Rechercher les articles sans catégorie
        uncategorized_items = frappe.get_all("Item",
            filters={
                "disabled": 0,
                "is_gnr_tracked": 0
            },
            fields=["name"],
            limit=50  # Traiter par petits lots
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
                    "is_gnr_tracked": 1
                })
                processed_count += 1
        
        if processed_count > 0:
            frappe.db.commit()
            update_statistics()
            
    except Exception as e:
        frappe.log_error(f"Erreur traitement catégorisation en attente: {str(e)}")