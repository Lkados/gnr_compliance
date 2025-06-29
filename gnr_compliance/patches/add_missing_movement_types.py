import frappe
import json

def execute():
    """Ajoute les types de mouvement manquants au DocType Mouvement GNR"""
    
    print("🔧 Ajout des types de mouvement manquants...")
    
    try:
        # Récupérer le DocType
        doctype = frappe.get_doc("DocType", "Mouvement GNR")
        
        # Trouver le champ type_mouvement
        for field in doctype.fields:
            if field.fieldname == "type_mouvement":
                # Ajouter les nouvelles options
                current_options = field.options.split("\n") if field.options else []
                new_options = ["Vente", "Achat", "Stock", "Transfert", "Entrée", "Sortie", "Production", "Consommation"]
                
                # Combiner et dédupliquer
                all_options = list(dict.fromkeys(current_options + new_options))
                
                # Mettre à jour
                field.options = "\n".join(all_options)
                
                # Sauvegarder
                doctype.save()
                frappe.db.commit()
                
                print(f"✅ Options mises à jour : {', '.join(all_options)}")
                break
        
        # Mettre à jour le cache
        frappe.clear_cache(doctype="Mouvement GNR")
        
    except Exception as e:
        print(f"❌ Erreur : {str(e)}")
        frappe.log_error(f"Erreur ajout types mouvement: {str(e)}")

# Pour exécuter manuellement
@frappe.whitelist()
def run_patch():
    """Exécute le patch manuellement"""
    execute()
    return {'success': True, 'message': 'Types de mouvement ajoutés'}