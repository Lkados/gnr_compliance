# ===================================================================
# OPTION 1 : Mettre dans gnr_compliance/setup/install.py (RECOMMANDÉ)
# ===================================================================

# gnr_compliance/setup/install.py
import frappe

def after_install():
    """Fonction appelée automatiquement après installation de l'app"""
    setup_gnr_roles_and_permissions()
    setup_gnr_workflows()
    print("✅ Configuration GNR terminée")

def setup_gnr_roles_and_permissions():
    """Configuration des rôles et permissions GNR"""
    
    # Configuration des rôles pour la conformité GNR
    roles_config = {
        "Opérateur GNR": {
            "permissions": {
                "Mouvement GNR": {"read": 1, "write": 1, "create": 1},
                "Déclaration Trimestrielle": {"read": 1},
                "Liste Clients Semestrielle": {"read": 1}
            }
        },
        "Responsable GNR": {
            "permissions": {
                "Mouvement GNR": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1},
                "Déclaration Trimestrielle": {"read": 1, "write": 1, "create": 1, "submit": 1},
                "Liste Clients Semestrielle": {"read": 1, "write": 1, "create": 1, "submit": 1}
            }
        },
        "Directeur Conformité": {
            "permissions": {
                "Mouvement GNR": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "delete": 1},
                "Déclaration Trimestrielle": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "delete": 1},
                "Liste Clients Semestrielle": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "delete": 1}
            }
        }
    }
    
    # 1. Créer les rôles
    for role_name, config in roles_config.items():
        create_role_if_not_exists(role_name)
    
    # 2. Configurer les permissions
    for role_name, config in roles_config.items():
        for doctype, permissions in config["permissions"].items():
            if doctype != "*":  # Éviter le wildcard pour l'instant
                setup_doctype_permissions(doctype, role_name, permissions)

def create_role_if_not_exists(role_name):
    """Créer un rôle s'il n'existe pas déjà"""
    if not frappe.db.exists("Role", role_name):
        role_doc = frappe.get_doc({
            "doctype": "Role",
            "role_name": role_name,
            "disabled": 0,
            "desk_access": 1,
            "is_custom": 1
        })
        role_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print(f"✓ Rôle créé: {role_name}")
    else:
        print(f"ℹ️  Rôle existe déjà: {role_name}")

def setup_doctype_permissions(doctype, role, permissions):
    """Configurer les permissions pour un DocType et un rôle"""
    try:
        # Vérifier que le DocType existe
        if not frappe.db.exists("DocType", doctype):
            print(f"⚠️  DocType n'existe pas encore: {doctype}")
            return
        
        # Supprimer les permissions existantes pour ce rôle sur ce doctype
        frappe.db.delete("DocPerm", {
            "parent": doctype,
            "role": role
        })
        
        # Créer la nouvelle permission
        permission = {
            "doctype": "DocPerm",
            "parent": doctype,
            "parenttype": "DocType", 
            "parentfield": "permissions",
            "role": role,
            "read": permissions.get("read", 0),
            "write": permissions.get("write", 0),
            "create": permissions.get("create", 0),
            "delete": permissions.get("delete", 0),
            "submit": permissions.get("submit", 0),
            "cancel": permissions.get("cancel", 0),
            "amend": permissions.get("amend", 0),
            "report": permissions.get("report", 1),
            "export": permissions.get("export", 0),
            "import": permissions.get("import", 0),
            "share": permissions.get("share", 0),
            "print": permissions.get("print", 1),
            "email": permissions.get("email", 0),
            "if_owner": 0
        }
        
        perm_doc = frappe.get_doc(permission)
        perm_doc.insert(ignore_permissions=True)
        
        print(f"✓ Permissions configurées: {doctype} -> {role}")
        
    except Exception as e:
        print(f"❌ Erreur configuration permission {doctype}/{role}: {str(e)}")

def setup_gnr_workflows():
    """Configuration des workflows GNR"""
    
    # Workflow pour les déclarations
    workflow_config = {
        "Déclaration Trimestrielle": {
            "workflow_name": "Workflow Déclaration Trimestrielle",
            "document_type": "Déclaration Trimestrielle",
            "workflow_state_field": "workflow_state",
            "is_active": 1,
            "send_email_alert": 1,
            "states": [
                {
                    "state": "Brouillon",
                    "doc_status": "0",
                    "allow_edit": "Responsable GNR"
                },
                {
                    "state": "En Révision", 
                    "doc_status": "0",
                    "allow_edit": "Directeur Conformité"
                },
                {
                    "state": "Approuvé",
                    "doc_status": "1",
                    "allow_edit": ""
                },
                {
                    "state": "Soumis",
                    "doc_status": "1",
                    "allow_edit": ""
                },
                {
                    "state": "Rejeté",
                    "doc_status": "0",
                    "allow_edit": "Responsable GNR"
                }
            ],
            "transitions": [
                {
                    "state": "Brouillon",
                    "action": "Soumettre pour Révision",
                    "next_state": "En Révision",
                    "allowed": "Responsable GNR",
                    "allow_self_approval": 0
                },
                {
                    "state": "En Révision",
                    "action": "Approuver",
                    "next_state": "Approuvé",
                    "allowed": "Directeur Conformité",
                    "allow_self_approval": 0
                },
                {
                    "state": "En Révision", 
                    "action": "Rejeter",
                    "next_state": "Rejeté",
                    "allowed": "Directeur Conformité",
                    "allow_self_approval": 0
                },
                {
                    "state": "Approuvé",
                    "action": "Soumettre Définitivement", 
                    "next_state": "Soumis",
                    "allowed": "Directeur Conformité",
                    "allow_self_approval": 1
                },
                {
                    "state": "Rejeté",
                    "action": "Reprendre en Brouillon",
                    "next_state": "Brouillon", 
                    "allowed": "Responsable GNR",
                    "allow_self_approval": 1
                }
            ]
        }
    }
    
    for doctype, config in workflow_config.items():
        create_workflow_if_not_exists(config)

def create_workflow_if_not_exists(workflow_config):
    """Créer un workflow s'il n'existe pas"""
    workflow_name = workflow_config["workflow_name"]
    
    if frappe.db.exists("Workflow", workflow_name):
        print(f"ℹ️  Workflow existe déjà: {workflow_name}")
        return
    
    try:
        # Vérifier que le DocType existe
        if not frappe.db.exists("DocType", workflow_config["document_type"]):
            print(f"⚠️  DocType n'existe pas encore: {workflow_config['document_type']}")
            return
        
        # Créer le workflow
        workflow_doc = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": workflow_name,
            "document_type": workflow_config["document_type"],
            "workflow_state_field": workflow_config["workflow_state_field"],
            "is_active": workflow_config.get("is_active", 1),
            "send_email_alert": workflow_config.get("send_email_alert", 1),
            "states": [],
            "transitions": []
        })
        
        # Ajouter les états
        for state in workflow_config["states"]:
            workflow_doc.append("states", {
                "state": state["state"],
                "doc_status": state["doc_status"],
                "allow_edit": state["allow_edit"]
            })
        
        # Ajouter les transitions
        for transition in workflow_config["transitions"]:
            workflow_doc.append("transitions", {
                "state": transition["state"],
                "action": transition["action"],
                "next_state": transition["next_state"],
                "allowed": transition["allowed"],
                "allow_self_approval": transition["allow_self_approval"]
            })
        
        workflow_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print(f"✓ Workflow créé: {workflow_name}")
        
    except Exception as e:
        print(f"❌ Erreur création workflow: {str(e)}")

# ===================================================================
# OPTION 2 : Ajouter dans hooks.py pour exécution post-installation
# ===================================================================

# gnr_compliance/hooks.py (AJOUTER À LA FIN)

# Fonction appelée après installation
after_install = "gnr_compliance.setup.install.after_install"

# ===================================================================
# OPTION 3 : Script d'exécution manuelle si nécessaire
# ===================================================================

# gnr_compliance/setup/manual_setup.py
import frappe

def setup_gnr_permissions_manually():
    """
    Fonction à exécuter manuellement si nécessaire
    
    Usage depuis la console ERPNext:
    bench --site [votre_site] console
    >>> from gnr_compliance.setup.manual_setup import setup_gnr_permissions_manually
    >>> setup_gnr_permissions_manually()
    """
    
    print("🚀 Début configuration manuelle GNR...")
    
    # Importer et exécuter les fonctions
    from gnr_compliance.setup.install import setup_gnr_roles_and_permissions, setup_gnr_workflows
    
    setup_gnr_roles_and_permissions()
    setup_gnr_workflows()
    
    frappe.db.commit()
    print("✅ Configuration manuelle GNR terminée")

# ===================================================================
# OPTION 4 : Via une page web d'administration
# ===================================================================

# gnr_compliance/www/setup_gnr.py (optionnel - page web pour setup)
import frappe

def get_context(context):
    # Page accessible via: http://votre_site/setup_gnr
    context.no_cache = 1
    context.title = "Configuration GNR"

@frappe.whitelist()
def run_gnr_setup():
    """API endpoint pour setup depuis interface web"""
    try:
        from gnr_compliance.setup.install import setup_gnr_roles_and_permissions, setup_gnr_workflows
        
        setup_gnr_roles_and_permissions()
        setup_gnr_workflows()
        
        frappe.db.commit()
        return {"status": "success", "message": "Configuration GNR terminée avec succès"}
        
    except Exception as e:
        frappe.log_error(f"Erreur setup GNR: {str(e)}")
        return {"status": "error", "message": f"Erreur: {str(e)}"}
