import frappe
from frappe.model.document import Document
import fnmatch

class GNRCategorySettings(Document):
    def validate(self):
        self.validate_unique_categories()
        
    def validate_unique_categories(self):
        """S'assurer que les noms de catégories sont uniques"""
        category_names = []
        for rule in self.category_rules:
            if rule.category_name in category_names:
                frappe.throw(f"Nom de catégorie dupliqué: {rule.category_name}")
            category_names.append(rule.category_name)
    
    def on_update(self):
        """Actions après mise à jour des paramètres"""
        # Vider le cache des paramètres
        frappe.cache().delete_value("gnr_settings")
        frappe.cache().delete_value("gnr_tracked_items")
        
        # Publier les mises à jour
        frappe.publish_realtime('gnr_settings_updated', {
            'enable_tracking': self.enable_category_tracking,
            'categories_count': len([r for r in self.category_rules if r.is_active])
        })
    
    @frappe.whitelist()
    def test_category_match(self, item_code):
        """Teste les règles de catégories contre un article spécifique"""
        try:
            item_doc = frappe.get_doc("Item", item_code)
            matched_category = self.find_matching_category(item_doc)
            
            return {
                'matched': bool(matched_category),
                'category': matched_category.category_name if matched_category else None,
                'priority': matched_category.priority if matched_category else None
            }
            
        except Exception as e:
            frappe.throw(f"Erreur lors du test: {str(e)}")
    
    def find_matching_category(self, item_doc):
        """Trouve la catégorie correspondante selon les règles"""
        matched_categories = []
        
        for rule in self.category_rules:
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
                    
            # Vérifier le chemin de catégorie dans le texte
            if rule.category_path and matches:
                path_parts = rule.category_path.split('/')
                item_text = f"{item_doc.item_name} {item_doc.item_group}".lower()
                
                if not all(part.lower() in item_text for part in path_parts):
                    matches = False
                    
            if matches:
                matched_categories.append((rule.priority or 10, rule))
        
        # Retourner la catégorie avec la priorité la plus élevée (valeur la plus faible)
        if matched_categories:
            matched_categories.sort(key=lambda x: x[0])
            return matched_categories[0][1]
        
        return None

    @frappe.whitelist()
    def get_active_category_rules(self):
        """Retourne les règles de catégories actives"""
        return [
            {
                'name': rule.category_name,
                'path': rule.category_path,
                'priority': rule.priority,
                'item_group_pattern': rule.item_group_pattern,
                'item_code_pattern': rule.item_code_pattern,
                'item_name_pattern': rule.item_name_pattern
            }
            for rule in self.category_rules
            if rule.is_active
        ]

# API pour accès externe
@frappe.whitelist()
def get_gnr_configuration():
    """API pour récupérer la configuration GNR"""
    try:
        settings = frappe.get_single("GNR Category Settings")
        return {
            'enabled': settings.enable_category_tracking,
            'auto_apply': settings.auto_apply_to_new_items,
            'categories': settings.get_active_category_rules(),
            'notifications': settings.notification_on_assignment
        }
    except Exception:
        return {
            'enabled': False,
            'auto_apply': False,
            'categories': [],
            'notifications': False
        }

@frappe.whitelist()
def update_category_rules(rules_json):
    """API pour mettre à jour les règles de catégories"""
    try:
        import json
        rules = json.loads(rules_json)
        
        settings = frappe.get_doc("GNR Category Settings")
        settings.category_rules = []
        
        for rule_data in rules:
            settings.append('category_rules', rule_data)
        
        settings.save()
        return {'status': 'success', 'message': 'Règles mises à jour avec succès'}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}