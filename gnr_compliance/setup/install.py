import frappe

def after_install():
    """Fonction appelée automatiquement après installation de l'app"""
    try:
        setup_gnr_roles_and_permissions()
        setup_default_categories()
        print("✅ Configuration GNR terminée")
    except Exception as e:
        print(f"⚠️ Erreur configuration: {e}")
        frappe.log_error(f"Erreur installation GNR: {str(e)}")

def setup_gnr_roles_and_permissions():
    """Configure les rôles et permissions GNR"""
    try:
        # Créer le rôle GNR Manager s'il n'existe pas
        if not frappe.db.exists("Role", "GNR Manager"):
            role_doc = frappe.get_doc({
                "doctype": "Role",
                "role_name": "GNR Manager",
                "desk_access": 1,
                "is_custom": 1
            })
            role_doc.insert(ignore_permissions=True)
            print("✅ Rôle 'GNR Manager' créé")
        
        # Ajouter les permissions pour les DocTypes GNR
        gnr_doctypes = [
            "GNR Category Settings",
            "GNR Category Rule", 
            "GNR Movement Log",
            "Declaration Trimestrielle",
            "Mouvement GNR"
        ]
        
        for doctype in gnr_doctypes:
            if frappe.db.exists("DocType", doctype):
                # Permissions pour GNR Manager
                if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": "GNR Manager"}):
                    perm_doc = frappe.get_doc({
                        "doctype": "Custom DocPerm",
                        "parent": doctype,
                        "parenttype": "DocType",
                        "parentfield": "permissions",
                        "role": "GNR Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                        "export": 1,
                        "report": 1
                    })
                    perm_doc.insert(ignore_permissions=True)
        
        frappe.db.commit()
        print("✅ Permissions GNR configurées")
        
    except Exception as e:
        print(f"❌ Erreur permissions: {str(e)}")

def setup_default_categories():
    """Configure les catégories par défaut"""
    try:
        # Attendre que les DocTypes soient installés
        if not frappe.db.exists("DocType", "GNR Category Settings"):
            print("⚠️ DocType GNR Category Settings pas encore installé, saut de la configuration")
            return
            
        # Créer les paramètres GNR Category Settings s'ils n'existent pas
        if not frappe.db.exists("GNR Category Settings"):
            settings = frappe.new_doc("GNR Category Settings")
            settings.enable_category_tracking = 1
            settings.auto_apply_to_new_items = 1
            settings.notification_on_assignment = 1
            
            # Catégories par défaut
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
                    "priority": 15,
                    "item_group_pattern": "*Combustible*",
                    "item_code_pattern": "*Fioul*",
                    "item_name_pattern": "*Fioul*"
                }
            ]
            
            for cat in default_categories:
                settings.append('category_rules', cat)
            
            settings.insert(ignore_permissions=True)
            frappe.db.commit()
            print("✅ Catégories GNR par défaut configurées")
        else:
            print("✅ Configuration GNR Category Settings déjà existante")
            
    except Exception as e:
        print(f"❌ Erreur configuration catégories: {str(e)}")
        frappe.log_error(f"Erreur setup catégories: {str(e)}")

# Fonction pour installation manuelle post-migration
def setup_categories_manually():
    """À exécuter manuellement après installation si nécessaire"""
    try:
        setup_default_categories()
        print("✅ Configuration manuelle des catégories terminée")
    except Exception as e:
        print(f"❌ Erreur configuration manuelle: {str(e)}")