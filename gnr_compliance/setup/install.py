# Votre code existant + ajout setup des catégories

import frappe

def after_install():
    """Fonction appelée automatiquement après installation de l'app"""
    setup_gnr_roles_and_permissions()
    setup_gnr_workflows()
    setup_default_categories()  # NOUVEAU
    print("✅ Configuration GNR terminée")

# ... VOTRE CODE EXISTANT INCHANGÉ ...

def setup_default_categories():
    """NOUVEAU: Configure les catégories par défaut"""
    try:
        # Créer les paramètres GNR Category Settings s'ils n'existent pas
        if not frappe.db.exists("GNR Category Settings"):
            settings = frappe.new_doc("GNR Category Settings")
            settings.enable_category_tracking = 1
            settings.auto_apply_to_new_items = 1
            settings.notification_on_assignment = 1
            
            # VOS catégories spécifiques
            default_categories = [
                {
                    "category_name": "GNR",
                    "category_path": "Combustibles/Carburants/GNR",
                    "is_active": 1,
                    "priority": 10,
                    "item_group_pattern": "*Combustible*",
                    "item_code_pattern": "*GNR*",
                    "item_name_pattern": "*GNR*"
                },
                {
                    "category_name": "Gazole",
                    "category_path": "Combustibles/Carburants/Gazole",
                    "is_active": 1,
                    "priority": 10,
                    "item_group_pattern": "*Combustible*",
                    "item_code_pattern": "*Gazole*",
                    "item_name_pattern": "*Gazole*"
                },
                {
                    "category_name": "AdBlue",
                    "category_path": "Combustibles/Adblue",
                    "is_active": 1,
                    "priority": 10,
                    "item_group_pattern": "*Combustible*",
                    "item_code_pattern": "*AdBlue*",
                    "item_name_pattern": "*AdBlue*"
                },
                {
                    "category_name": "Fioul Bio",
                    "category_path": "Combustibles/Fioul/Bio",
                    "is_active": 1,
                    "priority": 10,
                    "item_group_pattern": "*Combustible*",
                    "item_code_pattern": "*Fioul*Bio*",
                    "item_name_pattern": "*Fioul*Bio*"
                },
                {
                    "category_name": "Fioul Hiver",
                    "category_path": "Combustibles/Fioul/Hiver",
                    "is_active": 1,
                    "priority": 10,
                    "item_group_pattern": "*Combustible*",
                    "item_code_pattern": "*Fioul*Hiver*",
                    "item_name_pattern": "*Fioul*Hiver*"
                },
                {
                    "category_name": "Fioul Standard",
                    "category_path": "Combustibles/Fioul/Standard",
                    "is_active": 1,
                    "priority": 15,  # Priorité plus faible pour correspondre en dernier
                    "item_group_pattern": "*Combustible*",
                    "item_code_pattern": "*Fioul*",
                    "item_name_pattern": "*Fioul*"
                }
            ]
            
            for cat in default_categories:
                settings.append('category_rules', cat)
            
            settings.insert(ignore_permissions=True)
            print("✅ Catégories GNR par défaut configurées")
            
    except Exception as e:
        print(f"❌ Erreur configuration catégories: {str(e)}")
        frappe.log_error(f"Erreur setup catégories: {str(e)}")