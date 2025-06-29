import frappe
from frappe import _
from frappe.utils import flt, now_datetime, getdate
import logging

logger = logging.getLogger(__name__)

def get_quarter_from_date(date_obj):
    """Calcule le trimestre à partir d'une date"""
    if isinstance(date_obj, str):
        date_obj = getdate(date_obj)
    return str((date_obj.month - 1) // 3 + 1)

def get_semestre_from_date(date_obj):
    """Calcule le semestre à partir d'une date"""
    if isinstance(date_obj, str):
        date_obj = getdate(date_obj)
    return "1" if date_obj.month <= 6 else "2"

def capture_mouvement_stock(doc, method):
    """
    Capture des mouvements de stock pour produits GNR
    FONCTION PRINCIPALE - CORRIGÉE ET SIMPLIFIÉE
    """
    try:
        # Log pour debug
        frappe.logger().info(f"[GNR] Capture mouvement stock: {doc.name}, Type: {doc.stock_entry_type}")
        
        # Vérifier TOUS les types de Stock Entry (pas seulement certains)
        # Types courants : Material Transfer, Material Issue, Material Receipt, Material Transfer for Manufacture, etc.
        
        gnr_items = []
        gnr_count = 0
        
        # Parcourir tous les items du Stock Entry
        for item in doc.items:
            # Vérifier si l'article est tracké GNR - MÉTHODE CORRIGÉE
            is_gnr = check_if_gnr_item(item.item_code)
            
            if is_gnr:
                gnr_items.append(item)
                gnr_count += 1
                frappe.logger().info(f"[GNR] Article GNR détecté: {item.item_code}")
        
        if gnr_items:
            # Mettre à jour le compteur (si le champ existe)
            try:
                frappe.db.set_value("Stock Entry", doc.name, "gnr_items_detected", gnr_count, update_modified=False)
            except:
                pass  # Le champ n'existe peut-être pas
            
            # Créer les mouvements GNR pour chaque article
            movements_created = 0
            for item in gnr_items:
                if create_gnr_movement_from_stock(doc, item):
                    movements_created += 1
            
            # Marquer comme traité
            try:
                frappe.db.set_value("Stock Entry", doc.name, "gnr_categories_processed", 1, update_modified=False)
            except:
                pass
            
            frappe.db.commit()
            
            # Message de confirmation
            if movements_created > 0:
                frappe.msgprint(
                    f"✅ {movements_created} mouvement(s) GNR créé(s) depuis Stock Entry",
                    title="GNR Compliance - Stock",
                    indicator="green"
                )
            
            frappe.logger().info(f"[GNR] Traitement terminé: {movements_created} mouvements créés sur {len(gnr_items)} articles GNR")
            
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur capture mouvement stock {doc.name}: {str(e)}")
        frappe.log_error(f"Erreur traitement mouvement stock GNR: {str(e)}", "GNR Stock Error")

def check_if_gnr_item(item_code):
    """
    Vérifie si un article est un produit GNR - MÉTHODE AMÉLIORÉE
    """
    try:
        # Méthode 1 : Vérifier le champ is_gnr_tracked
        is_tracked = frappe.get_value("Item", item_code, "is_gnr_tracked")
        if is_tracked:
            return True
        
        # Méthode 2 : Vérifier par patterns (si le champ n'existe pas)
        item_doc = frappe.get_doc("Item", item_code)
        
        # Vérifier le code article
        code_lower = item_code.lower()
        gnr_keywords = ['gnr', 'gazole', 'gazoil', 'fioul', 'fuel', 'adblue', 'ad blue']
        for keyword in gnr_keywords:
            if keyword in code_lower:
                # Marquer automatiquement comme GNR
                try:
                    frappe.db.set_value("Item", item_code, {
                        "is_gnr_tracked": 1,
                        "gnr_tracked_category": keyword.upper()
                    })
                except:
                    pass
                return True
        
        # Vérifier le nom de l'article
        if item_doc.item_name:
            name_lower = item_doc.item_name.lower()
            for keyword in gnr_keywords:
                if keyword in name_lower:
                    try:
                        frappe.db.set_value("Item", item_code, {
                            "is_gnr_tracked": 1,
                            "gnr_tracked_category": keyword.upper()
                        })
                    except:
                        pass
                    return True
        
        # Vérifier le groupe d'articles
        if item_doc.item_group:
            group_lower = item_doc.item_group.lower()
            group_keywords = ['combustible', 'carburant', 'fuel', 'énergie']
            for keyword in group_keywords:
                if keyword in group_lower:
                    return True
        
        return False
        
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur vérification article {item_code}: {str(e)}")
        return False

def create_gnr_movement_from_stock(stock_doc, item):
    """
    Crée un mouvement GNR depuis un mouvement de stock - VERSION SIMPLIFIÉE
    """
    try:
        # Récupérer les données GNR de l'article
        item_doc = frappe.get_doc("Item", item.item_code)
        
        # Déterminer le type de mouvement GNR selon le type de Stock Entry
        movement_type_map = {
            "Material Receipt": "Entrée",
            "Material Issue": "Sortie",
            "Material Transfer": "Transfert",
            "Material Transfer for Manufacture": "Production",
            "Manufacture": "Production",
            "Repack": "Reconditionnement",
            "Send to Subcontractor": "Sortie",
            "Material Consumption for Manufacture": "Consommation"
        }
        
        # Type par défaut si non trouvé
        type_mouvement = movement_type_map.get(stock_doc.stock_entry_type, "Stock")
        
        # Pour les transferts, déterminer entrée/sortie selon l'entrepôt
        if stock_doc.stock_entry_type == "Material Transfer":
            if item.s_warehouse and not item.t_warehouse:
                type_mouvement = "Sortie"
            elif item.t_warehouse and not item.s_warehouse:
                type_mouvement = "Entrée"
        
        # Convertir la date
        posting_date = getdate(stock_doc.posting_date)
        
        # Récupérer le taux GNR
        taux_gnr = 0
        try:
            taux_gnr = flt(item_doc.gnr_tax_rate) or 0
        except:
            # Si le champ n'existe pas, utiliser un taux par défaut selon le produit
            if 'adblue' in item.item_code.lower():
                taux_gnr = 0  # AdBlue n'est pas taxé
            elif 'fioul' in item.item_code.lower():
                taux_gnr = 3.86  # Taux agricole par défaut
            else:
                taux_gnr = 24.81  # Taux standard par défaut
        
        # Créer le mouvement GNR
        mouvement_gnr = frappe.new_doc("Mouvement GNR")
        mouvement_gnr.update({
            "type_mouvement": type_mouvement,
            "date_mouvement": posting_date,
            "reference_document": "Stock Entry",
            "reference_name": stock_doc.name,
            "code_produit": item.item_code,
            "quantite": flt(item.qty),
            "prix_unitaire": flt(item.basic_rate or item.valuation_rate or 0),
            "taux_gnr": taux_gnr,
            "categorie_gnr": getattr(item_doc, 'gnr_tracked_category', 'GNR'),
            "trimestre": get_quarter_from_date(posting_date),
            "annee": posting_date.year,
            "semestre": get_semestre_from_date(posting_date)
        })
        
        # Calculer le montant de taxe GNR
        mouvement_gnr.montant_taxe_gnr = flt(mouvement_gnr.quantite * mouvement_gnr.taux_gnr)
        
        # Ajouter client/fournisseur si disponible
        if hasattr(stock_doc, 'customer') and stock_doc.customer:
            mouvement_gnr.client = stock_doc.customer
        elif hasattr(stock_doc, 'supplier') and stock_doc.supplier:
            mouvement_gnr.fournisseur = stock_doc.supplier
        
        # Insérer et soumettre
        mouvement_gnr.insert(ignore_permissions=True)
        
        if stock_doc.docstatus == 1:
            mouvement_gnr.submit()
            frappe.logger().info(f"[GNR] Mouvement GNR créé: {mouvement_gnr.name} pour {item.item_code} ({type_mouvement})")
            return True
        
        return False
        
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur création mouvement GNR pour {item.item_code}: {str(e)}")
        frappe.log_error(f"Erreur création mouvement GNR Stock: {str(e)}", "GNR Stock Movement Error")
        return False

def cancel_mouvement_stock(doc, method):
    """
    Annule les mouvements GNR associés à un Stock Entry annulé
    """
    try:
        frappe.logger().info(f"[GNR] Annulation mouvements pour Stock Entry: {doc.name}")
        
        # Annuler les mouvements GNR associés
        mouvements = frappe.get_all("Mouvement GNR",
                                   filters={
                                       "reference_document": "Stock Entry",
                                       "reference_name": doc.name,
                                       "docstatus": 1
                                   })
        
        cancelled_count = 0
        for mouvement in mouvements:
            try:
                mouvement_doc = frappe.get_doc("Mouvement GNR", mouvement.name)
                mouvement_doc.cancel()
                cancelled_count += 1
            except Exception as e:
                frappe.logger().error(f"[GNR] Erreur annulation mouvement {mouvement.name}: {str(e)}")
        
        if cancelled_count > 0:
            frappe.msgprint(
                f"✅ {cancelled_count} mouvement(s) GNR annulé(s)",
                title="GNR Compliance - Stock",
                indicator="orange"
            )
        
        frappe.logger().info(f"[GNR] {cancelled_count} mouvements GNR annulés pour {doc.name}")
        
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur annulation mouvements GNR pour {doc.name}: {str(e)}")

@frappe.whitelist()
def reprocess_stock_entries(from_date=None, to_date=None):
    """
    Retraite les Stock Entry pour capturer les mouvements GNR manqués
    """
    try:
        conditions = ["se.docstatus = 1"]
        values = []
        
        if from_date:
            conditions.append("se.posting_date >= %s")
            values.append(from_date)
        
        if to_date:
            conditions.append("se.posting_date <= %s")
            values.append(to_date)
        
        where_clause = " AND ".join(conditions)
        
        # Trouver les Stock Entry avec des articles GNR potentiels
        stock_entries = frappe.db.sql(f"""
            SELECT DISTINCT se.name, se.stock_entry_type, se.posting_date
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sed ON se.name = sed.parent
            WHERE {where_clause}
            AND NOT EXISTS (
                SELECT 1 FROM `tabMouvement GNR` m 
                WHERE m.reference_document = 'Stock Entry' 
                AND m.reference_name = se.name
                AND m.docstatus = 1
            )
            AND (
                sed.item_code LIKE '%GNR%'
                OR sed.item_code LIKE '%GAZOLE%'
                OR sed.item_code LIKE '%GAZOIL%'
                OR sed.item_code LIKE '%FIOUL%'
                OR sed.item_code LIKE '%FUEL%'
                OR sed.item_code LIKE '%ADBLUE%'
            )
            ORDER BY se.posting_date DESC
            LIMIT 100
        """, values, as_dict=True)
        
        processed = 0
        for entry in stock_entries:
            try:
                doc = frappe.get_doc("Stock Entry", entry.name)
                capture_mouvement_stock(doc, "reprocess")
                processed += 1
            except Exception as e:
                frappe.logger().error(f"[GNR] Erreur retraitement {entry.name}: {str(e)}")
        
        return {
            'success': True,
            'message': f"{processed} Stock Entry retraités sur {len(stock_entries)} trouvés",
            'processed': processed,
            'found': len(stock_entries)
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur retraitement Stock Entry: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def test_stock_capture(stock_entry_name):
    """
    Fonction de test pour capturer un Stock Entry spécifique
    """
    try:
        doc = frappe.get_doc("Stock Entry", stock_entry_name)
        capture_mouvement_stock(doc, "test")
        return {'success': True, 'message': 'Test exécuté - vérifiez les logs'}
    except Exception as e:
        return {'success': False, 'error': str(e)}