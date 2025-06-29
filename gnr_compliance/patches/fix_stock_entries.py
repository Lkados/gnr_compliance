import frappe
from frappe.utils import getdate, add_days

def execute():
    """Corrige la capture des mouvements de stock GNR"""
    
    print("🔧 Début de la correction des Stock Entry GNR...")
    
    try:
        # 1. S'assurer que les champs personnalisés existent sur Item
        ensure_item_custom_fields()
        
        # 2. Marquer automatiquement les articles GNR
        mark_gnr_items()
        
        # 3. Retraiter les Stock Entry récents
        reprocess_recent_stock_entries()
        
        print("✅ Correction terminée avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        frappe.log_error(f"Erreur patch Stock Entry GNR: {str(e)}")

def ensure_item_custom_fields():
    """S'assure que les champs GNR existent sur Item"""
    print("📋 Vérification des champs personnalisés...")
    
    # Liste des champs requis
    required_fields = [
        {
            "dt": "Item",
            "fieldname": "is_gnr_tracked",
            "label": "Article GNR Tracké",
            "fieldtype": "Check",
            "insert_after": "item_group"
        },
        {
            "dt": "Item",
            "fieldname": "gnr_tracked_category",
            "label": "Catégorie GNR",
            "fieldtype": "Data",
            "insert_after": "is_gnr_tracked"
        },
        {
            "dt": "Item",
            "fieldname": "gnr_tax_rate",
            "label": "Taux Taxe GNR (€/L)",
            "fieldtype": "Currency",
            "insert_after": "gnr_tracked_category"
        }
    ]
    
    for field in required_fields:
        if not frappe.db.exists("Custom Field", {"dt": field["dt"], "fieldname": field["fieldname"]}):
            cf = frappe.new_doc("Custom Field")
            cf.update(field)
            cf.insert(ignore_permissions=True)
            print(f"  ✅ Champ créé: {field['fieldname']}")
        else:
            print(f"  ✓ Champ existant: {field['fieldname']}")
    
    frappe.db.commit()

def mark_gnr_items():
    """Marque automatiquement les articles GNR"""
    print("🏷️ Marquage automatique des articles GNR...")
    
    # Patterns pour identifier les articles GNR
    patterns = [
        "%GNR%", "%GAZOLE%", "%GAZOIL%", "%FIOUL%", 
        "%FUEL%", "%ADBLUE%", "%AD BLUE%"
    ]
    
    count = 0
    for pattern in patterns:
        # Rechercher par code article
        items = frappe.db.sql("""
            SELECT name FROM `tabItem` 
            WHERE (item_code LIKE %s OR item_name LIKE %s)
            AND (is_gnr_tracked IS NULL OR is_gnr_tracked = 0)
        """, (pattern, pattern))
        
        for item in items:
            # Déterminer la catégorie
            item_code = item[0].upper()
            category = "GNR"
            tax_rate = 24.81  # Taux par défaut
            
            if "ADBLUE" in item_code or "AD BLUE" in item_code:
                category = "ADBLUE"
                tax_rate = 0  # Pas de taxe sur AdBlue
            elif "FIOUL" in item_code:
                category = "FIOUL"
                tax_rate = 3.86  # Taux agricole
            elif "GAZOLE" in item_code or "GAZOIL" in item_code:
                category = "GAZOLE"
                tax_rate = 24.81
            
            frappe.db.set_value("Item", item[0], {
                "is_gnr_tracked": 1,
                "gnr_tracked_category": category,
                "gnr_tax_rate": tax_rate
            })
            count += 1
    
    frappe.db.commit()
    print(f"  ✅ {count} articles marqués comme GNR")

def reprocess_recent_stock_entries():
    """Retraite les Stock Entry récents"""
    print("🔄 Retraitement des Stock Entry récents...")
    
    # Importer la fonction depuis le module stock
    from gnr_compliance.integrations.stock import reprocess_stock_entries
    
    # Retraiter les 30 derniers jours
    from_date = add_days(getdate(), -30)
    to_date = getdate()
    
    result = reprocess_stock_entries(from_date, to_date)
    
    if result.get('success'):
        print(f"  ✅ {result.get('processed', 0)} Stock Entry retraités")
    else:
        print(f"  ❌ Erreur: {result.get('error', 'Inconnue')}")

# Fonction pour exécution manuelle
@frappe.whitelist()
def run_fix():
    """Fonction pour exécuter le fix manuellement"""
    execute()
    return {'success': True, 'message': 'Correction appliquée'}