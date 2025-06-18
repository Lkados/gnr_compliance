from __future__ import annotations
import frappe
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def after_install() -> None:
    """Fonction appelée automatiquement après installation de l'app"""
    try:
        setup_gnr_roles_and_permissions()
        setup_default_categories()
        setup_default_tax_rates()
        create_custom_fields()
        
        logger.info("Configuration GNR terminée avec succès")
        
    except Exception as e:
        logger.error(f"Erreur configuration GNR: {e}")
        frappe.log_error(f"Erreur installation GNR: {str(e)}")

def setup_gnr_roles_and_permissions() -> None:
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
            logger.info("Rôle 'GNR Manager' créé")
        
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
                _add_doctype_permissions(doctype)
        
        frappe.db.commit()
        logger.info("Permissions GNR configurées")
        
    except Exception as e:
        logger.error(f"Erreur permissions: {e}")

def _add_doctype_permissions(doctype: str) -> None:
    """Ajoute les permissions pour un DocType"""
    permissions = [
        {
            "role": "GNR Manager",
            "perms": {"read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "report": 1}
        },
        {
            "role": "System Manager", 
            "perms": {"read": 1, "write": 1, "create": 1, "delete": 1, "export": 1, "report": 1}
        }
    ]
    
    for perm in permissions:
        if not frappe.db.exists("Custom DocPerm", {
            "parent": doctype, 
            "role": perm["role"]
        }):
            perm_doc = frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": perm["role"],
                **perm["perms"]
            })
            perm_doc.insert(ignore_permissions=True)

def setup_default_categories() -> None:
    """Configure les catégories par défaut"""
    try:
        if not frappe.db.exists("DocType", "GNR Category Settings"):
            logger.warning("DocType GNR Category Settings pas encore installé")
            return
            
        # Créer les paramètres GNR Category Settings s'ils n'existent pas
        if not frappe.db.exists("GNR Category Settings"):
            settings = frappe.new_doc("GNR Category Settings")
            settings.enable_category_tracking = 1
            settings.auto_apply_to_new_items = 1
            settings.notification_on_assignment = 1
            settings.cache_refresh_interval = 3600
            
            # Catégories par défaut optimisées
            default_categories = _get_default_categories()
            
            for cat in default_categories:
                settings.append('category_rules', cat)
            
            settings.insert(ignore_permissions=True)
            frappe.db.commit()
            logger.info("Catégories GNR par défaut configurées")
        else:
            logger.info("Configuration GNR Category Settings déjà existante")
            
    except Exception as e:
        logger.error(f"Erreur configuration catégories: {e}")

def _get_default_categories() -> List[Dict[str, Any]]:
    """Retourne les catégories par défaut"""
    return [
        {
            "category_name": "GNR",
            "category_path": "Combustibles/Carburants/GNR",
            "is_active": 1,
            "priority": 5,
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
            "priority": 8,
            "item_group_pattern": "*Combustible*",
            "item_code_pattern": "*Fioul*Bio*",
            "item_name_pattern": "*Fioul*Bio*"
        },
        {
            "category_name": "Fioul Hiver",
            "category_path": "Combustibles/Fioul/Hiver",
            "is_active": 1,
            "priority": 8,
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

def setup_default_tax_rates() -> None:
    """Configure les taux de taxe par défaut"""
    try:
        # Créer le DocType GNR Tax Rate s'il n'existe pas
        if not frappe.db.exists("DocType", "GNR Tax Rate"):
            return
            
        default_rates = [
            {"category": "GNR", "rate": 18.82, "description": "Taux standard GNR"},
            {"category": "Gazole", "rate": 59.4, "description": "Taux standard Gazole"},
            {"category": "Fioul Bio", "rate": 15.0, "description": "Taux réduit Fioul Bio"},
            {"category": "Fioul Hiver", "rate": 18.82, "description": "Taux standard Fioul Hiver"},
            {"category": "Fioul Standard", "rate": 18.82, "description": "Taux standard Fioul"},
        ]
        
        for rate_data in default_rates:
            if not frappe.db.exists("GNR Tax Rate", {"category": rate_data["category"]}):
                tax_rate = frappe.new_doc("GNR Tax Rate")
                tax_rate.update({
                    **rate_data,
                    "is_active": 1,
                    "effective_from": frappe.utils.today()
                })
                tax_rate.insert(ignore_permissions=True)
        
        frappe.db.commit()
        logger.info("Taux de taxe GNR par défaut configurés")
        
    except Exception as e:
        logger.error(f"Erreur configuration taux de taxe: {e}")

def create_custom_fields() -> None:
    """Crée les champs personnalisés"""
    try:
        # Les champs personnalisés sont maintenant définis dans hooks.py
        # Cette fonction peut être utilisée pour des champs additionnels
        logger.info("Champs personnalisés traités via hooks.py")
        
    except Exception as e:
        logger.error(f"Erreur création champs personnalisés: {e}")

# ==========================================
# FICHIER: doctype/gnr_category_settings/gnr_category_settings.py - DocType Optimisé
# ==========================================

from __future__ import annotations
import frappe
from frappe.model.document import Document
import fnmatch
import json
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class GNRCategorySettings(Document):
    """Configuration des catégories GNR avec validation et cache automatique"""
    
    def validate(self) -> None:
        """Validation des données avant sauvegarde"""
        self.validate_unique_categories()
        self.validate_priority_values()
        self.validate_cache_interval()
        
    def validate_unique_categories(self) -> None:
        """S'assurer que les noms de catégories sont uniques"""
        category_names = []
        for rule in self.category_rules:
            if rule.category_name in category_names:
                frappe.throw(f"Nom de catégorie dupliqué: {rule.category_name}")
            category_names.append(rule.category_name)
    
    def validate_priority_values(self) -> None:
        """Valider les valeurs de priorité"""
        for rule in self.category_rules:
            if rule.priority and (rule.priority < 1 or rule.priority > 100):
                frappe.throw(f"Priorité invalide pour {rule.category_name}: doit être entre 1 et 100")
    
    def validate_cache_interval(self) -> None:
        """Valider l'intervalle de cache"""
        if self.cache_refresh_interval and self.cache_refresh_interval < 300:
            frappe.throw("L'intervalle de rafraîchissement du cache ne peut pas être inférieur à 5 minutes")
    
    def on_update(self) -> None:
        """Actions après mise à jour des paramètres"""
        self._clear_cache()
        self._publish_updates()
        
    def _clear_cache(self) -> None:
        """Vider les caches GNR"""
        cache_keys = [
            "gnr_settings",
            "gnr_tracked_items", 
            "gnr_tracked_categories",
            "gnr_category_rules"
        ]
        
        for key in cache_keys:
            frappe.cache().delete_value(key)
    
    def _publish_updates(self) -> None:
        """Publier les mises à jour en temps réel"""
        frappe.publish_realtime('gnr_settings_updated', {
            'enable_tracking': self.enable_category_tracking,
            'categories_count': len([r for r in self.category_rules if r.is_active]),
            'last_update': frappe.utils.now()
        })
    
    @frappe.whitelist()
    def test_category_match(self, item_code: str) -> Dict[str, Any]:
        """
        Teste les règles de catégories contre un article spécifique
        
        Args:
            item_code: Code de l'article à tester
            
        Returns:
            Résultat du test avec correspondance trouvée
        """
        try:
            item_doc = frappe.get_doc("Item", item_code)
            matched_category = self.find_matching_category(item_doc)
            
            return {
                'matched': bool(matched_category),
                'category': matched_category.category_name if matched_category else None,
                'priority': matched_category.priority if matched_category else None,
                'patterns_matched': self._get_matched_patterns(item_doc, matched_category) if matched_category else []
            }
            
        except Exception as e:
            logger.error(f"Erreur test catégorie pour {item_code}: {e}")
            frappe.throw(f"Erreur lors du test: {str(e)}")
    
    def _get_matched_patterns(self, item_doc: Any, rule: Any) -> List[str]:
        """Retourne les patterns qui ont correspondu"""
        matched = []
        
        if rule.item_group_pattern and fnmatch.fnmatch(item_doc.item_group or "", rule.item_group_pattern):
            matched.append(f"Groupe: {rule.item_group_pattern}")
        
        if rule.item_code_pattern and fnmatch.fnmatch(item_doc.item_code or "", rule.item_code_pattern):
            matched.append(f"Code: {rule.item_code_pattern}")
            
        if rule.item_name_pattern and fnmatch.fnmatch(item_doc.item_name or "", rule.item_name_pattern):
            matched.append(f"Nom: {rule.item_name_pattern}")
            
        return matched
    
    def find_matching_category(self, item_doc: Any) -> Optional[Any]:
        """
        Trouve la catégorie correspondante selon les règles
        
        Args:
            item_doc: Document Item à analyser
            
        Returns:
            Règle de catégorie correspondante ou None
        """
        from gnr_compliance.utils.category_detector import find_matching_category
        return find_matching_category(item_doc, self.category_rules)

    @frappe.whitelist()
    def get_active_category_rules(self) -> List[Dict[str, Any]]:
        """Retourne les règles de catégories actives"""
        return [
            {
                'name': rule.category_name,
                'path': rule.category_path,
                'priority': rule.priority,
                'item_group_pattern': rule.item_group_pattern,
                'item_code_pattern': rule.item_code_pattern,
                'item_name_pattern': rule.item_name_pattern,
                'brand_pattern': rule.brand_pattern,
                'supplier_pattern': rule.supplier_pattern,
                'additional_filters': rule.additional_filters
            }
            for rule in self.category_rules
            if rule.is_active
        ]
    
    @frappe.whitelist()
    def export_configuration(self) -> Dict[str, Any]:
        """Exporte la configuration complète"""
        return {
            'settings': {
                'enable_category_tracking': self.enable_category_tracking,
                'auto_apply_to_new_items': self.auto_apply_to_new_items,
                'notification_on_assignment': self.notification_on_assignment,
                'cache_refresh_interval': self.cache_refresh_interval
            },
            'category_rules': self.get_active_category_rules(),
            'export_timestamp': frappe.utils.now(),
            'version': '1.0.0'
        }

# API pour accès externe
@frappe.whitelist()
def get_gnr_configuration() -> Dict[str, Any]:
    """API pour récupérer la configuration GNR"""
    try:
        settings = frappe.get_single("GNR Category Settings")
        return {
            'enabled': settings.enable_category_tracking,
            'auto_apply': settings.auto_apply_to_new_items,
            'categories': settings.get_active_category_rules(),
            'notifications': settings.notification_on_assignment,
            'cache_interval': settings.cache_refresh_interval,
            'total_tracked_items': settings.total_tracked_items,
            'last_cache_refresh': settings.last_cache_refresh
        }
    except Exception as e:
        logger.error(f"Erreur récupération configuration: {e}")
        return {
            'enabled': False,
            'auto_apply': False,
            'categories': [],
            'notifications': False,
            'cache_interval': 3600,
            'total_tracked_items': 0,
            'last_cache_refresh': None
        }

@frappe.whitelist()
def update_category_rules(rules_json: str) -> Dict[str, str]:
    """API pour mettre à jour les règles de catégories"""
    try:
        rules = json.loads(rules_json)
        
        settings = frappe.get_doc("GNR Category Settings")
        settings.category_rules = []
        
        for rule_data in rules:
            settings.append('category_rules', rule_data)
        
        settings.save()
        return {'status': 'success', 'message': 'Règles mises à jour avec succès'}
        
    except Exception as e:
        logger.error(f"Erreur mise à jour règles: {e}")
        return {'status': 'error', 'message': str(e)}

# ==========================================
# FICHIER: doctype/gnr_movement_log/gnr_movement_log.py - Log Mouvements Optimisé
# ==========================================

from __future__ import annotations
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class GNRMovementLog(Document):
    """Log des mouvements GNR avec validation et indexation automatique"""
    
    def before_insert(self) -> None:
        """Actions avant insertion"""
        self._set_defaults()
        self._validate_reference()
        
    def _set_defaults(self) -> None:
        """Définir les valeurs par défaut"""
        if not self.user:
            self.user = frappe.session.user
        if not self.timestamp:
            self.timestamp = now_datetime()
    
    def _validate_reference(self) -> None:
        """Valider la référence du document"""
        if self.reference_doctype and self.reference_name:
            if not frappe.db.exists(self.reference_doctype, self.reference_name):
                frappe.throw(f"Document de référence introuvable: {self.reference_doctype} {self.reference_name}")
    
    def validate(self) -> None:
        """Validation des données"""
        self._validate_item_code()
        self._validate_movement_type()
        self._validate_quantities()
        
    def _validate_item_code(self) -> None:
        """Valider le code article"""
        if self.item_code and not frappe.db.exists("Item", self.item_code):
            frappe.throw(f"Article introuvable: {self.item_code}")
    
    def _validate_movement_type(self) -> None:
        """Valider le type de mouvement"""
        valid_types = ["Category Assignment", "Stock Movement", "Sale", "Purchase", "Transfer"]
        if self.movement_type not in valid_types:
            frappe.throw(f"Type de mouvement invalide: {self.movement_type}")
    
    def _validate_quantities(self) -> None:
        """Valider les quantités"""
        if self.quantity and self.quantity < 0:
            frappe.throw("La quantité ne peut pas être négative")
    
    def on_update(self) -> None:
        """Actions après mise à jour"""
        self._update_movement_cache()
    
    def _update_movement_cache(self) -> None:
        """Mettre à jour le cache des mouvements"""
        if self.gnr_category:
            cache_key = f"gnr_movements_{self.gnr_category}"
            # Invalider le cache pour forcer un rechargement
            frappe.cache().delete_value(cache_key)
    
    @classmethod
    def create_log(cls, 
                   reference_doctype: str,
                   reference_name: str,
                   item_code: str,
                   gnr_category: str,
                   movement_type: str,
                   quantity: float = 0,
                   amount: float = 0,
                   warehouse: Optional[str] = None,
                   details: Optional[Dict[str, Any]] = None) -> str:
        """
        Méthode helper pour créer un log
        
        Args:
            reference_doctype: Type de document source
            reference_name: Nom du document source
            item_code: Code de l'article
            gnr_category: Catégorie GNR
            movement_type: Type de mouvement
            quantity: Quantité
            amount: Montant
            warehouse: Entrepôt
            details: Détails additionnels
            
        Returns:
            Nom du document créé
        """
        try:
            log_entry = frappe.new_doc("GNR Movement Log")
            log_entry.update({
                'reference_doctype': reference_doctype,
                'reference_name': reference_name,
                'item_code': item_code,
                'gnr_category': gnr_category,
                'movement_type': movement_type,
                'quantity': quantity,
                'amount': amount,
                'warehouse': warehouse,
                'user': frappe.session.user,
                'timestamp': now_datetime(),
                'details': json.dumps(details) if details else None
            })
            log_entry.insert(ignore_permissions=True)
            
            return log_entry.name
            
        except Exception as e:
            logger.error(f"Erreur création log mouvement: {e}")
            raise

# API pour requêtes et statistiques
@frappe.whitelist()
def get_movement_statistics(category: Optional[str] = None, 
                           days: int = 30) -> Dict[str, Any]:
    """
    Récupère les statistiques des mouvements
    
    Args:
        category: Catégorie spécifique (optionnel)
        days: Nombre de jours à analyser
        
    Returns:
        Statistiques des mouvements
    """
    try:
        filters = {
            "timestamp": [">=", frappe.utils.add_days(frappe.utils.now(), -days)]
        }
        
        if category:
            filters["gnr_category"] = category
            
        movements = frappe.get_all("GNR Movement Log",
                                 filters=filters,
                                 fields=["movement_type", "quantity", "amount", "gnr_category"])
        
        stats = {
            'total_movements': len(movements),
            'total_quantity': sum(m.quantity or 0 for m in movements),
            'total_amount': sum(m.amount or 0 for m in movements),
            'by_type': {},
            'by_category': {}
        }
        
        # Grouper par type
        for movement in movements:
            mov_type = movement.movement_type
            if mov_type not in stats['by_type']:
                stats['by_type'][mov_type] = {'count': 0, 'quantity': 0, 'amount': 0}
            
            stats['by_type'][mov_type]['count'] += 1
            stats['by_type'][mov_type]['quantity'] += movement.quantity or 0
            stats['by_type'][mov_type]['amount'] += movement.amount or 0
        
        # Grouper par catégorie
        for movement in movements:
            cat = movement.gnr_category
            if cat and cat not in stats['by_category']:
                stats['by_category'][cat] = {'count': 0, 'quantity': 0, 'amount': 0}
            
            if cat:
                stats['by_category'][cat]['count'] += 1
                stats['by_category'][cat]['quantity'] += movement.quantity or 0
                stats['by_category'][cat]['amount'] += movement.amount or 0
        
        return stats
        
    except Exception as e:
        logger.error(f"Erreur statistiques mouvements: {e}")
        return {}

@frappe.whitelist()
def get_recent_movements(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Récupère les mouvements récents
    
    Args:
        limit: Nombre maximum de mouvements à retourner
        
    Returns:
        Liste des mouvements récents
    """
    try:
        return frappe.get_all("GNR Movement Log",
                            order_by="timestamp desc",
                            limit=limit,
                            fields=["*"])
    except Exception as e:
        logger.error(f"Erreur récupération mouvements récents: {e}")
        return []