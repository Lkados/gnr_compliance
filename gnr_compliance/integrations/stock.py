import frappe
from frappe import _
from frappe.utils import flt, now_datetime, getdate
import logging
from gnr_compliance.utils.unit_conversions import convert_to_litres, get_item_unit

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
    Vérifie si un article est un produit GNR en se basant sur le groupe d'article
    """
    try:
        # Liste des groupes GNR valides
        GNR_ITEM_GROUPS = [
            "Combustibles/Carburants/GNR",
            "Combustibles/Carburants/Gazole", 
            "Combustibles/Adblue",
            "Combustibles/Fioul/Bio",
            "Combustibles/Fioul/Hiver",
            "Combustibles/Fioul/Standard"
        ]
        
        # Méthode 1 : Vérifier le champ is_gnr_tracked
        is_tracked = frappe.get_value("Item", item_code, "is_gnr_tracked")
        if is_tracked:
            return True
        
        # Méthode 2 : Vérifier le groupe d'article
        item_group = frappe.get_value("Item", item_code, "item_group")
        
        if item_group in GNR_ITEM_GROUPS:
            # Marquer automatiquement comme GNR
            category, tax_rate = get_category_and_rate_from_group(item_group)
            
            try:
                frappe.db.set_value("Item", item_code, {
                    "is_gnr_tracked": 1,
                    "gnr_tracked_category": category,
                    "gnr_tax_rate": tax_rate
                })
                frappe.logger().info(f"[GNR] Article {item_code} marqué automatiquement comme GNR (groupe: {item_group})")
            except:
                pass
                
            return True
        
        return False
        
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur vérification article {item_code}: {str(e)}")
        return False

def get_category_and_rate_from_group(item_group):
    """Retourne la catégorie et le taux selon le groupe"""
    mapping = {
        "Combustibles/Carburants/GNR": ("GNR", 24.81),
        "Combustibles/Carburants/Gazole": ("GAZOLE", 24.81),
        "Combustibles/Adblue": ("ADBLUE", 0),
        "Combustibles/Fioul/Bio": ("FIOUL_BIO", 3.86),
        "Combustibles/Fioul/Hiver": ("FIOUL_HIVER", 3.86),
        "Combustibles/Fioul/Standard": ("FIOUL_STANDARD", 3.86)
    }
    
    return mapping.get(item_group, ("GNR", 24.81))

def create_gnr_movement_from_stock(stock_doc, item):
    """
    Crée un mouvement GNR depuis un mouvement de stock
    AVEC CONVERSION EN LITRES
    """
    try:
        # ... (début du code identique)
        
        # NOUVEAU : Récupérer l'unité de mesure
        item_unit = item.uom or get_item_unit(item.item_code)
        
        # NOUVEAU : Convertir en litres
        quantity_in_litres = convert_to_litres(item.qty, item_unit)
        
        # Log de la conversion
        if item_unit != "L" and item_unit != "l":
            frappe.logger().info(f"[GNR] Conversion Stock: {item.qty} {item_unit} = {quantity_in_litres} litres")
        
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

@frappe.whitelist()
def debug_stock_entry(stock_entry_name):
    """
    Debug détaillé d'un Stock Entry spécifique
    """
    try:
        se = frappe.get_doc("Stock Entry", stock_entry_name)
        
        print(f"\n🔍 Debug Stock Entry: {stock_entry_name}")
        print(f"  Type: {se.stock_entry_type}")
        print(f"  Date: {se.posting_date}")
        print(f"  Statut: {se.docstatus}")
        
        print(f"\n  📦 Articles:")
        gnr_count = 0
        for item in se.items:
            is_gnr = frappe.get_value("Item", item.item_code, "is_gnr_tracked")
            item_group = frappe.get_value("Item", item.item_code, "item_group")
            
            if is_gnr:
                gnr_count += 1
                print(f"    ✅ {item.item_code} - Qty: {item.qty} - Groupe: {item_group}")
            else:
                print(f"    ❌ {item.item_code} - Qty: {item.qty} - Groupe: {item_group}")
        
        # Vérifier les mouvements GNR existants
        existing = frappe.get_all("Mouvement GNR", 
                                 filters={
                                     "reference_document": "Stock Entry",
                                     "reference_name": stock_entry_name
                                 },
                                 fields=["name", "docstatus", "code_produit", "quantite"])
        
        print(f"\n  📊 Mouvements GNR existants: {len(existing)}")
        for mov in existing:
            status = "Soumis" if mov.docstatus == 1 else "Brouillon"
            print(f"    - {mov.name}: {mov.code_produit} - {mov.quantite} [{status}]")
        
        return {
            'name': stock_entry_name,
            'gnr_items': gnr_count,
            'existing_movements': len(existing)
        }
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return {'error': str(e)}
    
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