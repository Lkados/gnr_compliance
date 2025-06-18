import frappe

def setup_default_categories():
    """Configure les catégories par défaut"""
    
    # Vérifier si les paramètres existent déjà
    if not frappe.db.exists("GNR Category Settings"):
        settings = frappe.new_doc("GNR Category Settings")
        settings.enable_category_tracking = 1
        
        # Vos catégories par défaut
        default_categories = [
            {
                "category_name": "GNR",
                "category_path": "Combustibles/Carburants/GNR",
                "is_active": 1,
                "priority": 10,
                "item_group_pattern": "*Combustible*",
                "item_code_pattern": "*GNR*"
            },
            {
                "category_name": "Gazole",
                "category_path": "Combustibles/Carburants/Gazole", 
                "is_active": 1,
                "priority": 10,
                "item_group_pattern": "*Combustible*",
                "item_code_pattern": "*Gazole*"
            },
            {
                "category_name": "AdBlue",
                "category_path": "Combustibles/Adblue",
                "is_active": 1,
                "priority": 10,
                "item_group_pattern": "*Combustible*",
                "item_code_pattern": "*AdBlue*"
            },
            {
                "category_name": "Fioul Bio",
                "category_path": "Combustibles/Fioul/Bio",
                "is_active": 1,
                "priority": 10,
                "item_group_pattern": "*Combustible*",
                "item_code_pattern": "*Fioul*Bio*"
            },
            {
                "category_name": "Fioul Hiver",
                "category_path": "Combustibles/Fioul/Hiver",
                "is_active": 1,
                "priority": 10,
                "item_group_pattern": "*Combustible*",
                "item_code_pattern": "*Fioul*Hiver*"
            },
            {
                "category_name": "Fioul Standard",
                "category_path": "Combustibles/Fioul/Standard",
                "is_active": 1,
                "priority": 15,
                "item_group_pattern": "*Combustible*",
                "item_code_pattern": "*Fioul*"
            }
        ]
        
        for cat in default_categories:
            settings.append('category_rules', cat)
        
        settings.insert(ignore_permissions=True)
        print("✅ Catégories GNR par défaut configurées")

@frappe.whitelist()
def apply_categories_to_existing_items():
    """Applique les catégories aux articles existants"""
    settings = frappe.get_single("GNR Category Settings")
    
    if not settings.enable_category_tracking:
        return {'updated_count': 0}
    
    # Récupérer tous les articles
    items = frappe.get_all("Item", fields=["name", "item_code", "item_name", "item_group"])
    updated_count = 0
    
    for item in items:
        item_doc = frappe.get_doc("Item", item.name)
        matched_category = settings.find_matching_category(item_doc)
        
        if matched_category:
            frappe.db.set_value("Item", item.name, {
                "gnr_tracked_category": matched_category.category_name,
                "is_gnr_tracked": 1
            })
            updated_count += 1
    
    frappe.db.commit()
    return {'updated_count': updated_count}