# gnr_compliance/utils/gnr_utilities.py
import frappe
from frappe import _
from frappe.utils import nowdate, getdate, now_datetime
import json

@frappe.whitelist()
def submit_pending_gnr_movements():
    """
    Soumet automatiquement tous les mouvements GNR en brouillon
    
    Returns:
        Dictionnaire avec le résumé des soumissions
    """
    try:
        # Récupérer tous les mouvements GNR en brouillon
        draft_movements = frappe.get_all("Mouvement GNR",
                                        filters={"docstatus": 0},
                                        fields=["name", "type_mouvement", "code_produit", "date_mouvement"])
        
        if not draft_movements:
            return {
                'success': True,
                'message': 'Aucun mouvement GNR en brouillon trouvé',
                'submitted_count': 0,
                'failed_count': 0
            }
        
        submitted_count = 0
        failed_count = 0
        failed_movements = []
        
        for movement in draft_movements:
            try:
                movement_doc = frappe.get_doc("Mouvement GNR", movement.name)
                
                # Validation avant soumission
                if validate_movement_before_submit(movement_doc):
                    movement_doc.submit()
                    submitted_count += 1
                    frappe.logger().info(f"Mouvement GNR soumis: {movement.name}")
                else:
                    failed_count += 1
                    failed_movements.append({
                        'name': movement.name,
                        'reason': 'Validation échouée'
                    })
                    
            except Exception as e:
                failed_count += 1
                failed_movements.append({
                    'name': movement.name,
                    'reason': str(e)
                })
                frappe.log_error(f"Erreur soumission mouvement {movement.name}: {str(e)}")
        
        # Commit les changements
        frappe.db.commit()
        
        result = {
            'success': True,
            'message': f'Traitement terminé: {submitted_count} soumis, {failed_count} échecs',
            'submitted_count': submitted_count,
            'failed_count': failed_count,
            'total_processed': len(draft_movements)
        }
        
        if failed_movements:
            result['failed_movements'] = failed_movements
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Erreur soumission en lot des mouvements GNR: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'submitted_count': 0,
            'failed_count': 0
        }

def validate_movement_before_submit(movement_doc):
    """
    Valide un mouvement GNR avant soumission
    
    Args:
        movement_doc: Document Mouvement GNR
        
    Returns:
        bool: True si valide, False sinon
    """
    try:
        # Vérifications de base
        if not movement_doc.code_produit:
            return False
            
        if not movement_doc.quantite or movement_doc.quantite <= 0:
            return False
            
        if not movement_doc.date_mouvement:
            return False
            
        # Vérifier que l'article existe toujours
        if not frappe.db.exists("Item", movement_doc.code_produit):
            return False
            
        # Vérifier que le client/fournisseur existe si spécifié
        if movement_doc.client and not frappe.db.exists("Customer", movement_doc.client):
            return False
            
        if movement_doc.fournisseur and not frappe.db.exists("Supplier", movement_doc.fournisseur):
            return False
        
        return True
        
    except Exception as e:
        frappe.log_error(f"Erreur validation mouvement {movement_doc.name}: {str(e)}")
        return False

@frappe.whitelist()
def get_gnr_movements_summary(from_date=None, to_date=None):
    """
    Récupère un résumé des mouvements GNR
    
    Args:
        from_date: Date de début (optionnel)
        to_date: Date de fin (optionnel)
        
    Returns:
        Dictionnaire avec le résumé
    """
    try:
        # Dates par défaut (mois en cours)
        if not from_date:
            from_date = nowdate().replace(day=1)  # Premier jour du mois
        if not to_date:
            to_date = nowdate()
        
        # Convertir en objets date
        from_date = getdate(from_date)
        to_date = getdate(to_date)
        
        # Requête pour les statistiques
        summary = frappe.db.sql("""
            SELECT 
                docstatus,
                type_mouvement,
                COUNT(*) as count,
                SUM(quantite) as total_quantity,
                SUM(montant_taxe_gnr) as total_tax
            FROM `tabMouvement GNR`
            WHERE date_mouvement BETWEEN %s AND %s
            GROUP BY docstatus, type_mouvement
            ORDER BY docstatus, type_mouvement
        """, (from_date, to_date), as_dict=True)
        
        # Organiser les données
        result = {
            'period': {'from': str(from_date), 'to': str(to_date)},
            'draft': {'count': 0, 'movements': {}},
            'submitted': {'count': 0, 'movements': {}},
            'cancelled': {'count': 0, 'movements': {}},
            'totals': {'count': 0, 'quantity': 0, 'tax': 0}
        }
        
        status_map = {0: 'draft', 1: 'submitted', 2: 'cancelled'}
        
        for item in summary:
            status_key = status_map.get(item.docstatus, 'unknown')
            
            if status_key in result:
                result[status_key]['count'] += item.count
                result[status_key]['movements'][item.type_mouvement] = {
                    'count': item.count,
                    'quantity': item.total_quantity or 0,
                    'tax': item.total_tax or 0
                }
                
                # Totaux globaux (seulement les soumis)
                if status_key == 'submitted':
                    result['totals']['count'] += item.count
                    result['totals']['quantity'] += item.total_quantity or 0
                    result['totals']['tax'] += item.total_tax or 0
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Erreur résumé mouvements GNR: {str(e)}")
        return {'error': str(e)}

@frappe.whitelist()
def fix_missing_periods():
    """
    Corrige les mouvements GNR sans trimestre/semestre définis
    
    Returns:
        Nombre de mouvements corrigés
    """
    try:
        # Trouver les mouvements sans période définie
        movements = frappe.db.sql("""
            SELECT name, date_mouvement
            FROM `tabMouvement GNR`
            WHERE (trimestre IS NULL OR trimestre = '' OR annee IS NULL OR annee = 0)
            AND date_mouvement IS NOT NULL
        """, as_dict=True)
        
        fixed_count = 0
        
        for movement in movements:
            try:
                date_obj = getdate(movement.date_mouvement)
                
                # Calculer trimestre et semestre
                trimestre = str((date_obj.month - 1) // 3 + 1)
                semestre = "1" if date_obj.month <= 6 else "2"
                
                # Mettre à jour
                frappe.db.set_value("Mouvement GNR", movement.name, {
                    "trimestre": trimestre,
                    "annee": date_obj.year,
                    "semestre": semestre
                })
                
                fixed_count += 1
                
            except Exception as e:
                frappe.log_error(f"Erreur correction période pour {movement.name}: {str(e)}")
        
        frappe.db.commit()
        
        return {
            'success': True,
            'fixed_count': fixed_count,
            'message': f'{fixed_count} mouvements corrigés'
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur correction périodes: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def cleanup_invalid_movements():
    """
    Nettoie les mouvements GNR invalides (articles supprimés, etc.)
    
    Returns:
        Résumé du nettoyage
    """
    try:
        # Trouver les mouvements avec des articles inexistants
        invalid_movements = frappe.db.sql("""
            SELECT m.name, m.code_produit
            FROM `tabMouvement GNR` m
            LEFT JOIN `tabItem` i ON m.code_produit = i.name
            WHERE i.name IS NULL
            AND m.docstatus = 0
        """, as_dict=True)
        
        deleted_count = 0
        
        for movement in invalid_movements:
            try:
                frappe.delete_doc("Mouvement GNR", movement.name, ignore_permissions=True)
                deleted_count += 1
                frappe.logger().info(f"Mouvement GNR invalide supprimé: {movement.name}")
                
            except Exception as e:
                frappe.log_error(f"Erreur suppression mouvement {movement.name}: {str(e)}")
        
        frappe.db.commit()
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'message': f'{deleted_count} mouvements invalides supprimés'
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur nettoyage mouvements: {str(e)}")
        return {'success': False, 'error': str(e)}

# Tâche planifiée pour soumettre automatiquement les mouvements en brouillon
def auto_submit_pending_movements():
    """Tâche planifiée pour soumettre les mouvements en attente"""
    try:
        # Soumettre les mouvements de plus de 5 minutes en brouillon
        old_drafts = frappe.db.sql("""
            SELECT name
            FROM `tabMouvement GNR`
            WHERE docstatus = 0
            AND modified < DATE_SUB(NOW(), INTERVAL 5 MINUTE)
            LIMIT 50
        """, as_list=True)
        
        submitted = 0
        for draft in old_drafts:
            try:
                doc = frappe.get_doc("Mouvement GNR", draft[0])
                if validate_movement_before_submit(doc):
                    doc.submit()
                    submitted += 1
            except Exception as e:
                frappe.log_error(f"Auto-submit failed for {draft[0]}: {str(e)}")
        
        if submitted > 0:
            frappe.log_error(f"Auto-submitted {submitted} GNR movements")
            
    except Exception as e:
        frappe.log_error(f"Erreur auto-submit mouvements GNR: {str(e)}")

# API pour l'interface utilisateur
@frappe.whitelist()
def get_dashboard_data():
    """Données pour le tableau de bord GNR"""
    try:
        today = nowdate()
        
        # Statistiques du jour
        daily_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN docstatus = 0 THEN 1 ELSE 0 END) as draft,
                SUM(CASE WHEN docstatus = 1 THEN 1 ELSE 0 END) as submitted,
                SUM(CASE WHEN docstatus = 1 THEN montant_taxe_gnr ELSE 0 END) as total_tax
            FROM `tabMouvement GNR`
            WHERE DATE(date_mouvement) = %s
        """, (today,), as_dict=True)[0]
        
        # Mouvements récents
        recent_movements = frappe.get_all("Mouvement GNR",
            filters={"date_mouvement": today},
            fields=["name", "type_mouvement", "code_produit", "quantite", "docstatus"],
            order_by="modified desc",
            limit=10
        )
        
        return {
            'daily_stats': daily_stats,
            'recent_movements': recent_movements,
            'last_updated': now_datetime()
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur données tableau de bord: {str(e)}")
        return {'error': str(e)}