import frappe
from frappe import _
from frappe.utils import flt, now_datetime, getdate
import logging
from gnr_compliance.utils.unit_conversions import convert_to_litres, get_item_unit
from gnr_compliance.utils.date_utils import get_quarter_from_date, get_semestre_from_date

logger = logging.getLogger(__name__)

def capture_mouvement_stock(doc, method):
    """
    Capture des mouvements de stock pour produits GNR
    FONCTION PRINCIPALE - CORRIGÉE ET SIMPLIFIÉE
    """
    try:
        # Log pour debug
        frappe.logger().info(f"[GNR] Capture mouvement stock: {doc.name}, Type: {doc.stock_entry_type}")
        
        # Traiter TOUS les types de Stock Entry sans restriction
        # Accepte tous les types: Sales, Purchase, Custom types, etc.
        
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
    Vérifie si un article est GNR basé UNIQUEMENT sur le marquage manuel
    """
    try:
        # Vérifier uniquement le champ is_gnr_tracked
        is_tracked = frappe.get_value("Item", item_code, "is_gnr_tracked")
        return bool(is_tracked)
        
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur vérification article {item_code}: {str(e)}")
        return False


def create_gnr_movement_from_stock(stock_doc, item):
    """
    Crée un mouvement GNR depuis un mouvement de stock
    AVEC CONVERSION EN LITRES
    """
    try:
        # Déterminer le type de mouvement
        type_mouvement = determine_movement_type(stock_doc.stock_entry_type, item)
        
        if not type_mouvement:
            return False
        
        # Récupérer les informations de l'article
        item_doc = frappe.get_doc("Item", item.item_code)
        
        # Date de posting
        posting_date = getdate(stock_doc.posting_date)
        
        # Taux GNR de l'article
        taux_gnr = getattr(item_doc, 'gnr_tax_rate', 0) or 0
        
        # NOUVEAU : Récupérer l'unité de mesure
        item_unit = item.uom or get_item_unit(item.item_code)
        
        # NOUVEAU : Convertir en litres
        quantity_in_litres = convert_to_litres(item.qty, item_unit)
        
        # Log de la conversion avec prix
        if item_unit != "L" and item_unit != "l":
            prix_original_par_unite = (item.basic_rate or item.valuation_rate or 0) / item.qty if item.qty else 0
            prix_par_litre = (item.basic_rate or item.valuation_rate or 0) / (quantity_in_litres / item.qty) if item.qty else 0
            frappe.logger().info(f"[GNR] Conversion Stock: {item.qty} {item_unit} = {quantity_in_litres} litres")
            frappe.logger().info(f"[GNR] Prix Stock: {prix_original_par_unite:.2f}€/{item_unit} → {prix_par_litre:.4f}€/L")
        
        # Créer le mouvement GNR
        mouvement_gnr = frappe.new_doc("Mouvement GNR")
        mouvement_gnr.update({
            "type_mouvement": type_mouvement,
            "date_mouvement": posting_date,
            "reference_document": "Stock Entry",
            "reference_name": stock_doc.name,
            "code_produit": item.item_code,
            "quantite": quantity_in_litres,  # EN LITRES
            "prix_unitaire": flt(item.basic_rate or item.valuation_rate or 0) / (quantity_in_litres / item.qty) if item.qty else 0,
            "taux_gnr": taux_gnr,
            "categorie_gnr": getattr(item_doc, 'gnr_tracked_category', 'GNR'),
            "trimestre": get_quarter_from_date(posting_date),
            "annee": posting_date.year,
            "semestre": get_semestre_from_date(posting_date)
        })
        
        # Calculer le montant de taxe GNR (en litres)
        mouvement_gnr.montant_taxe_gnr = flt(mouvement_gnr.quantite * mouvement_gnr.taux_gnr)
        
        # Sauvegarder
        mouvement_gnr.insert(ignore_permissions=True)
        
        try:
            mouvement_gnr.submit()
            frappe.logger().info(f"[GNR] Mouvement stock créé et soumis: {mouvement_gnr.name}")
            return True
        except Exception as submit_error:
            frappe.log_error(f"Erreur soumission mouvement stock {mouvement_gnr.name}: {str(submit_error)}")
            return True  # Compter comme créé même si pas soumis
            
    except Exception as e:
        frappe.log_error(f"Erreur création mouvement GNR depuis stock: {str(e)}")
        return False

def determine_movement_type(stock_entry_type, item):
    """Détermine le type de mouvement GNR selon le type de Stock Entry"""
    
    # Déterminer selon les entrepôts source/cible (logique principale)
    if item.s_warehouse and item.t_warehouse:
        return "Transfert"
    elif item.t_warehouse and not item.s_warehouse:
        return "Entrée"
    elif item.s_warehouse and not item.t_warehouse:
        return "Sortie"
    
    # Si aucun entrepôt n'est défini, déterminer selon le type de Stock Entry
    # Utiliser une logique plus flexible basée sur les mots-clés
    stock_entry_type_lower = stock_entry_type.lower() if stock_entry_type else ""
    
    if any(word in stock_entry_type_lower for word in ["receipt", "receive", "purchase", "buy", "entrée"]):
        return "Entrée"
    elif any(word in stock_entry_type_lower for word in ["issue", "sale", "sell", "delivery", "sortie", "consumption"]):
        return "Sortie"
    elif any(word in stock_entry_type_lower for word in ["transfer", "move", "transfert"]):
        return "Transfert"
    elif any(word in stock_entry_type_lower for word in ["manufacture", "production", "repack", "assembly"]):
        return "Production"
    
    # Par défaut, essayer de déterminer selon le contexte
    # Si on ne peut pas déterminer, utiliser "Stock" comme type générique
    return "Stock"

def cancel_mouvement_stock(doc, method):
    """Annule les mouvements GNR lors de l'annulation d'un Stock Entry"""
    try:
        # Trouver les mouvements GNR liés
        movements = frappe.get_all("Mouvement GNR",
                                  filters={
                                      "reference_document": "Stock Entry",
                                      "reference_name": doc.name,
                                      "docstatus": ["!=", 2]  # Pas déjà annulés
                                  })
        
        movements_cancelled = 0
        for movement in movements:
            mov_doc = frappe.get_doc("Mouvement GNR", movement.name)
            if mov_doc.docstatus == 1:  # Si soumis, annuler
                mov_doc.cancel()
            else:  # Si brouillon, supprimer
                mov_doc.delete()
            movements_cancelled += 1
        
        if movements_cancelled > 0:
            frappe.msgprint(
                f"✅ {movements_cancelled} mouvement(s) GNR annulé(s)",
                title="GNR Compliance",
                indicator="orange"
            )
            
    except Exception as e:
        frappe.log_error(f"Erreur annulation GNR pour Stock Entry {doc.name}: {str(e)}")

@frappe.whitelist()
def reprocess_stock_entries(from_date=None, to_date=None):
    """
    Retraite les Stock Entry pour capturer les mouvements GNR manqués
    """
    try:
        # Construction de la requête SQL pour chercher les articles MARQUÉS GNR
        conditions = ["se.docstatus = 1"]
        values = []
        
        if from_date:
            conditions.append("se.posting_date >= %s")
            values.append(from_date)
        
        if to_date:
            conditions.append("se.posting_date <= %s")
            values.append(to_date)
        
        where_clause = " AND ".join(conditions)
        
        # Requête CORRIGÉE - cherche les articles marqués is_gnr_tracked = 1
        query = f"""
            SELECT DISTINCT 
                se.name, 
                se.stock_entry_type, 
                se.posting_date,
                COUNT(sed.name) as nb_items_gnr
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sed ON se.name = sed.parent
            INNER JOIN `tabItem` i ON sed.item_code = i.name
            WHERE {where_clause}
            AND i.is_gnr_tracked = 1
            AND NOT EXISTS (
                SELECT 1 FROM `tabMouvement GNR` m 
                WHERE m.reference_document = 'Stock Entry' 
                AND m.reference_name = se.name
                AND m.docstatus = 1
            )
            GROUP BY se.name
            ORDER BY se.posting_date DESC
            LIMIT 100
        """
        
        stock_entries = frappe.db.sql(query, values, as_dict=True)
        
        frappe.logger().info(f"[GNR] Trouvé {len(stock_entries)} Stock Entry à traiter")
        
        processed = 0
        errors = []
        for entry in stock_entries:
            try:
                frappe.logger().info(f"[GNR] Traitement de {entry.name} avec {entry.nb_items_gnr} articles GNR")
                doc = frappe.get_doc("Stock Entry", entry.name)
                capture_mouvement_stock(doc, "reprocess")
                processed += 1
            except Exception as e:
                error_msg = f"Erreur {entry.name}: {str(e)}"
                frappe.logger().error(f"[GNR] {error_msg}")
                errors.append(error_msg)
        
        return {
            'success': True,
            'message': f"{processed} Stock Entry retraités sur {len(stock_entries)} trouvés",
            'processed': processed,
            'found': len(stock_entries),
            'errors': errors if errors else None
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur retraitement Stock Entry: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def find_stock_entries_with_gnr(from_date=None, to_date=None):
    """
    Fonction pour trouver et lister les Stock Entry avec articles GNR
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
        
        # Chercher TOUS les Stock Entry avec articles GNR
        query = f"""
            SELECT 
                se.name,
                se.stock_entry_type,
                se.posting_date,
                GROUP_CONCAT(DISTINCT sed.item_code) as items_gnr,
                COUNT(DISTINCT sed.item_code) as nb_items,
                SUM(sed.qty) as total_qty,
                EXISTS(
                    SELECT 1 FROM `tabMouvement GNR` m 
                    WHERE m.reference_document = 'Stock Entry' 
                    AND m.reference_name = se.name
                    AND m.docstatus = 1
                ) as has_gnr_movement
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sed ON se.name = sed.parent
            INNER JOIN `tabItem` i ON sed.item_code = i.name
            WHERE {where_clause}
            AND i.is_gnr_tracked = 1
            GROUP BY se.name
            ORDER BY se.posting_date DESC
            LIMIT 20
        """
        
        entries = frappe.db.sql(query, values, as_dict=True)
        
        print(f"\n📋 Stock Entry avec articles GNR trouvés: {len(entries)}")
        for entry in entries:
            status = "✅ Traité" if entry.has_gnr_movement else "❌ Non traité"
            print(f"\n  - {entry.name} ({entry.posting_date})")
            print(f"    Type: {entry.stock_entry_type}")
            print(f"    Articles GNR: {entry.items_gnr}")
            print(f"    Quantité totale: {entry.total_qty}")
            print(f"    Statut: {status}")
        
        return entries
        
    except Exception as e:
        frappe.log_error(f"Erreur recherche Stock Entry GNR: {str(e)}")
        return []

