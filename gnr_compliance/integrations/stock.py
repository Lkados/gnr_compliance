import frappe
from frappe import _
from frappe.utils import flt, now_datetime, getdate
import logging
from gnr_compliance.utils.unit_conversions import convert_to_litres, get_item_unit

logger = logging.getLogger(__name__)

# Groupes d'articles GNR valides (SEULEMENT pour la détection)
GNR_ITEM_GROUPS = [
    "Combustibles/Carburants/GNR",
    "Combustibles/Carburants/Gazole", 
    "Combustibles/Adblue",
    "Combustibles/Fioul/Bio",
    "Combustibles/Fioul/Hiver",
    "Combustibles/Fioul/Standard"
]

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

def detect_gnr_category_from_item(item_code, item_name=""):
    """Détecte la catégorie GNR depuis le code/nom d'article"""
    text = f"{item_code} {item_name or ''}".upper()
    
    if "ADBLUE" in text or "AD BLUE" in text or "AD-BLUE" in text:
        return "ADBLUE"
    elif "FIOUL" in text or "FUEL" in text:
        if "BIO" in text:
            return "FIOUL_BIO"
        elif "HIVER" in text or "WINTER" in text:
            return "FIOUL_HIVER"
        else:
            return "FIOUL_STANDARD"
    elif "GAZOLE" in text or "GAZOIL" in text or "DIESEL" in text:
        return "GAZOLE"
    elif "GNR" in text:
        return "GNR"
    else:
        return "GNR"  # Par défaut

def get_historical_rate_for_item(item_code):
    """Récupère le taux historique le plus récent pour un article"""
    try:
        result = frappe.db.sql("""
            SELECT taux_gnr 
            FROM `tabMouvement GNR` 
            WHERE code_produit = %s 
            AND taux_gnr IS NOT NULL 
            AND taux_gnr > 0.1
            AND taux_gnr < 50
            AND docstatus = 1
            ORDER BY date_mouvement DESC, creation DESC
            LIMIT 1
        """, (item_code,))
        
        return result[0][0] if result else None
    except:
        return None

def get_default_rate_by_category(category):
    """TAUX PAR DÉFAUT - UTILISÉS SEULEMENT EN DERNIER RECOURS"""
    default_rates = {
        "ADBLUE": 0.0,      # AdBlue non taxé
        "FIOUL_BIO": 3.86,  # Fioul agricole bio
        "FIOUL_HIVER": 3.86, # Fioul agricole hiver
        "FIOUL_STANDARD": 3.86, # Fioul agricole standard
        "GAZOLE": 24.81,    # Gazole routier
        "GNR": 24.81        # GNR standard
    }
    return default_rates.get(category, 24.81)

def get_real_tax_rate_for_stock_item(item_code, stock_item=None):
    """
    RÉCUPÈRE LE VRAI TAUX GNR POUR UN ARTICLE DEPUIS LES MOUVEMENTS DE STOCK
    
    Args:
        item_code: Code de l'article
        stock_item: Ligne de Stock Entry Detail (optionnel)
    
    Returns:
        float: Taux GNR réel en €/L
    """
    try:
        # 1. PRIORITÉ 1: Taux défini sur l'article maître
        item_rate = frappe.get_value("Item", item_code, "gnr_tax_rate")
        if item_rate and 0.1 <= item_rate <= 50:
            frappe.logger().info(f"[GNR] Taux depuis article maître: {item_rate}€/L")
            return item_rate
        
        # 2. PRIORITÉ 2: Dernier taux utilisé dans l'historique
        historical_rate = get_historical_rate_for_item(item_code)
        if historical_rate:
            frappe.logger().info(f"[GNR] Taux historique: {historical_rate}€/L")
            return historical_rate
        
        # 3. PRIORITÉ 3: Analyser le nom/code de l'article
        item_name = ""
        if stock_item and hasattr(stock_item, 'item_name'):
            item_name = stock_item.item_name
        elif not item_name:
            item_name = frappe.get_value("Item", item_code, "item_name") or ""
        
        category = detect_gnr_category_from_item(item_code, item_name)
        
        # 4. PRIORITÉ 4: Chercher dans les factures récentes de cet article
        recent_invoice_rate = get_recent_invoice_rate_for_item(item_code)
        if recent_invoice_rate:
            frappe.logger().info(f"[GNR] Taux depuis factures récentes: {recent_invoice_rate}€/L")
            return recent_invoice_rate
        
        # 5. PRIORITÉ 5: Analyser le prix du mouvement de stock actuel
        if stock_item:
            stock_rate = calculate_tax_rate_from_stock_price(stock_item, category)
            if stock_rate and 0.1 <= stock_rate <= 50:
                frappe.logger().info(f"[GNR] Taux calculé depuis prix stock: {stock_rate}€/L")
                return stock_rate
        
        # 6. DERNIER RECOURS: Taux par défaut selon la catégorie
        default_rate = get_default_rate_by_category(category)
        frappe.logger().warning(f"[GNR] Taux par défaut utilisé pour {item_code} ({category}): {default_rate}€/L")
        return default_rate
        
    except Exception as e:
        frappe.log_error(f"Erreur récupération taux réel pour article stock {item_code}: {str(e)}")
        return 0.0

def get_recent_invoice_rate_for_item(item_code):
    """
    Récupère le taux GNR depuis les factures récentes de cet article
    """
    try:
        # Chercher dans les mouvements GNR créés depuis des factures récentes
        result = frappe.db.sql("""
            SELECT m.taux_gnr
            FROM `tabMouvement GNR` m
            WHERE m.code_produit = %s
            AND m.reference_document IN ('Purchase Invoice', 'Sales Invoice')
            AND m.taux_gnr IS NOT NULL
            AND m.taux_gnr > 0.1
            AND m.taux_gnr < 50
            AND m.docstatus = 1
            AND m.date_mouvement >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
            ORDER BY m.date_mouvement DESC
            LIMIT 1
        """, (item_code,))
        
        return result[0][0] if result else None
    except:
        return None

def calculate_tax_rate_from_stock_price(stock_item, category):
    """
    Essaie de calculer un taux GNR à partir du prix du mouvement de stock
    Basé sur des heuristiques et la catégorie détectée
    """
    try:
        # Récupérer le prix unitaire du mouvement
        unit_price = 0
        if hasattr(stock_item, 'basic_rate') and stock_item.basic_rate:
            unit_price = stock_item.basic_rate
        elif hasattr(stock_item, 'valuation_rate') and stock_item.valuation_rate:
            unit_price = stock_item.valuation_rate
        elif hasattr(stock_item, 'rate') and stock_item.rate:
            unit_price = stock_item.rate
        
        if unit_price <= 0:
            return None
        
        # Convertir en prix par litre si nécessaire
        item_unit = stock_item.uom or get_item_unit(stock_item.item_code)
        if stock_item.qty > 0:
            quantity_in_litres = convert_to_litres(stock_item.qty, item_unit)
            price_per_litre = unit_price * stock_item.qty / quantity_in_litres if quantity_in_litres > 0 else unit_price
        else:
            price_per_litre = unit_price
        
        # Heuristiques basées sur le prix et la catégorie
        if category == "ADBLUE":
            # AdBlue généralement entre 0.80€ et 1.50€/L, pas de taxe
            return 0.0
        elif category in ["FIOUL_BIO", "FIOUL_HIVER", "FIOUL_STANDARD"]:
            # Fioul agricole: environ 10-15% du prix est la taxe
            if 0.60 <= price_per_litre <= 1.20:  # Prix typique fioul
                estimated_tax = price_per_litre * 0.12  # ~12% du prix
                if 2.0 <= estimated_tax <= 5.0:
                    return estimated_tax
        elif category in ["GAZOLE", "GNR"]:
            # GNR/Gazole: environ 15-20% du prix est la taxe
            if 1.20 <= price_per_litre <= 2.00:  # Prix typique GNR
                estimated_tax = price_per_litre * 0.18  # ~18% du prix
                if 15.0 <= estimated_tax <= 35.0:
                    return estimated_tax
        
        return None
        
    except Exception as e:
        frappe.logger().error(f"Erreur calcul taux depuis prix stock: {str(e)}")
        return None

def capture_mouvement_stock(doc, method):
    """
    Capture des mouvements de stock pour produits GNR
    FONCTION PRINCIPALE - AVEC RÉCUPÉRATION DES VRAIS TAUX
    """
    try:
        # Log pour debug
        frappe.logger().info(f"[GNR] Capture mouvement stock avec VRAIS TAUX: {doc.name}, Type: {doc.stock_entry_type}")
        
        # Vérifier TOUS les types de Stock Entry
        gnr_items = []
        gnr_count = 0
        
        # Parcourir tous les items du Stock Entry
        for item in doc.items:
            # Vérifier si l'article est tracké GNR
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
            
            # Créer les mouvements GNR pour chaque article avec VRAIS TAUX
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
                    f"✅ {movements_created} mouvement(s) GNR créé(s) depuis Stock Entry avec TAUX RÉELS",
                    title="GNR Compliance - Stock",
                    indicator="green"
                )
            
            frappe.logger().info(f"[GNR] Traitement terminé avec TAUX RÉELS: {movements_created} mouvements créés sur {len(gnr_items)} articles GNR")
            
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur capture mouvement stock avec taux réels {doc.name}: {str(e)}")
        frappe.log_error(f"Erreur traitement mouvement stock GNR avec taux réels: {str(e)}", "GNR Stock Error")

def check_if_gnr_item(item_code):
    """
    Vérifie si un article est un produit GNR en se basant sur le groupe d'article
    """
    try:
        # Méthode 1 : Vérifier le champ is_gnr_tracked
        is_tracked = frappe.get_value("Item", item_code, "is_gnr_tracked")
        if is_tracked:
            return True
        
        # Méthode 2 : Vérifier le groupe d'article
        item_group = frappe.get_value("Item", item_code, "item_group")
        
        if item_group in GNR_ITEM_GROUPS:
            # Marquer automatiquement comme GNR
            category = detect_gnr_category_from_item(item_code)
            
            try:
                frappe.db.set_value("Item", item_code, {
                    "is_gnr_tracked": 1,
                    "gnr_tracked_category": category
                    # NE PAS définir gnr_tax_rate ici - il sera récupéré depuis les sources réelles
                })
                frappe.logger().info(f"[GNR] Article {item_code} marqué automatiquement comme GNR (groupe: {item_group})")
            except:
                pass
                
            return True
        
        return False
        
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur vérification article {item_code}: {str(e)}")
        return False

def create_gnr_movement_from_stock(stock_doc, item):
    """
    Crée un mouvement GNR depuis un mouvement de stock
    AVEC RÉCUPÉRATION DES VRAIS TAUX ET CONVERSION EN LITRES
    """
    try:
        # Déterminer le type de mouvement
        type_mouvement = determine_movement_type(stock_doc.stock_entry_type, item)
        
        if not type_mouvement:
            return False
        
        # Date de posting
        posting_date = getdate(stock_doc.posting_date)
        
        # RÉCUPÉRER L'UNITÉ ET CONVERTIR EN LITRES
        item_unit = item.uom or get_item_unit(item.item_code)
        quantity_in_litres = convert_to_litres(item.qty, item_unit)
        
        # Log de la conversion
        if item_unit != "L" and item_unit != "l":
            frappe.logger().info(f"[GNR] Conversion Stock: {item.qty} {item_unit} = {quantity_in_litres} litres")
        
        # RÉCUPÉRER LE VRAI TAUX GNR - PRIORITÉS:
        # 1. Depuis le taux défini sur l'article
        # 2. Depuis l'historique des mouvements
        # 3. Depuis l'analyse du prix du mouvement de stock
        # 4. Analyser le nom de l'article
        # 5. Taux par défaut en dernier recours
        
        taux_gnr_reel = get_real_tax_rate_for_stock_item(item.item_code, item)
        
        # PRIX UNITAIRE RÉEL DEPUIS LE MOUVEMENT DE STOCK (par litre)
        prix_unitaire_reel = 0
        if hasattr(item, 'basic_rate') and item.basic_rate:
            prix_unitaire_reel = item.basic_rate / (quantity_in_litres / item.qty) if item.qty else item.basic_rate
        elif hasattr(item, 'valuation_rate') and item.valuation_rate:
            prix_unitaire_reel = item.valuation_rate / (quantity_in_litres / item.qty) if item.qty else item.valuation_rate
        elif hasattr(item, 'rate') and item.rate:
            prix_unitaire_reel = item.rate / (quantity_in_litres / item.qty) if item.qty else item.rate
        
        # Détecter la catégorie
        gnr_category = detect_gnr_category_from_item(item.item_code, getattr(item, 'item_name', ''))
        
        # Créer le mouvement GNR
        mouvement_gnr = frappe.new_doc("Mouvement GNR")
        mouvement_gnr.update({
            "type_mouvement": type_mouvement,
            "date_mouvement": posting_date,
            "reference_document": "Stock Entry",
            "reference_name": stock_doc.name,
            "code_produit": item.item_code,
            "quantite": quantity_in_litres,  # EN LITRES
            "prix_unitaire": prix_unitaire_reel,  # PRIX RÉEL PAR LITRE
            "taux_gnr": taux_gnr_reel,  # TAUX RÉEL
            "categorie_gnr": gnr_category,
            "trimestre": get_quarter_from_date(posting_date),
            "annee": posting_date.year,
            "semestre": get_semestre_from_date(posting_date)
        })
        
        # Calculer le montant de taxe GNR (en litres)
        mouvement_gnr.montant_taxe_gnr = flt(mouvement_gnr.quantite * mouvement_gnr.taux_gnr)
        
        # Ajouter des informations de traçabilité
        mouvement_gnr.db_set("custom_original_qty", item.qty)
        mouvement_gnr.db_set("custom_original_uom", item_unit)
        mouvement_gnr.db_set("custom_stock_entry_type", stock_doc.stock_entry_type)
        
        # Sauvegarder
        mouvement_gnr.insert(ignore_permissions=True)
        
        try:
            mouvement_gnr.submit()
            frappe.logger().info(f"[GNR] Mouvement stock créé avec TAUX RÉEL: {mouvement_gnr.name} - {quantity_in_litres}L à {taux_gnr_reel}€/L")
            return True
        except Exception as submit_error:
            frappe.log_error(f"Erreur soumission mouvement stock {mouvement_gnr.name}: {str(submit_error)}")
            return True  # Compter comme créé même si pas soumis
            
    except Exception as e:
        frappe.log_error(f"Erreur création mouvement GNR depuis stock avec taux réels: {str(e)}")
        return False

def determine_movement_type(stock_entry_type, item):
    """Détermine le type de mouvement GNR selon le type de Stock Entry"""
    
    # Mapping des types de Stock Entry vers types de mouvement GNR
    type_mapping = {
        "Material Receipt": "Entrée",
        "Material Issue": "Sortie", 
        "Material Transfer": "Transfert",
        "Manufacture": "Production",
        "Repack": "Production",
        "Send to Subcontractor": "Sortie",
        "Material Transfer for Manufacture": "Transfert"
    }
    
    # Déterminer selon les entrepôts source/cible
    if hasattr(item, 's_warehouse') and hasattr(item, 't_warehouse'):
        if item.s_warehouse and item.t_warehouse:
            return "Transfert"
        elif item.t_warehouse and not item.s_warehouse:
            return "Entrée"
        elif item.s_warehouse and not item.t_warehouse:
            return "Sortie"
    
    # Utiliser le mapping par défaut
    return type_mapping.get(stock_entry_type, "Stock")

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
    AVEC RÉCUPÉRATION DES VRAIS TAUX
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
        
        # Requête pour chercher les articles marqués is_gnr_tracked = 1
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
        
        frappe.logger().info(f"[GNR] Trouvé {len(stock_entries)} Stock Entry à retraiter avec vrais taux")
        
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
            'message': f"{processed} Stock Entry retraités avec vrais taux sur {len(stock_entries)} trouvés",
            'processed': processed,
            'found': len(stock_entries),
            'errors': errors if errors else None
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur retraitement Stock Entry avec vrais taux: {str(e)}")
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
                # Récupérer le taux réel pour cet article
                taux_reel = get_real_tax_rate_for_stock_item(item.item_code, item)
                print(f"    ✅ {item.item_code} - Qty: {item.qty} - Groupe: {item_group} - Taux réel: {taux_reel}€/L")
            else:
                print(f"    ❌ {item.item_code} - Qty: {item.qty} - Groupe: {item_group}")
        
        # Vérifier les mouvements GNR existants
        existing = frappe.get_all("Mouvement GNR", 
                                 filters={
                                     "reference_document": "Stock Entry",
                                     "reference_name": stock_entry_name
                                 },
                                 fields=["name", "docstatus", "code_produit", "quantite", "taux_gnr"])
        
        print(f"\n  📊 Mouvements GNR existants: {len(existing)}")
        for mov in existing:
            status = "Soumis" if mov.docstatus == 1 else "Brouillon"
            print(f"    - {mov.name}: {mov.code_produit} - {mov.quantite}L à {mov.taux_gnr}€/L [{status}]")
        
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
        return {'success': True, 'message': 'Test exécuté avec vrais taux - vérifiez les logs'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def recalculer_taux_stock_movements(limite=50):
    """
    Recalcule les taux GNR pour les mouvements créés depuis des Stock Entry
    """
    try:
        # Récupérer les mouvements de stock avec taux suspects
        mouvements_stock = frappe.db.sql("""
            SELECT name, code_produit, taux_gnr, quantite, reference_name
            FROM `tabMouvement GNR`
            WHERE docstatus = 1
            AND reference_document = 'Stock Entry'
            AND taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81)  -- Taux par défaut suspects
            ORDER BY creation DESC
            LIMIT %s
        """, (limite,), as_dict=True)
        
        corriges = 0
        echecs = 0
        
        for mouvement in mouvements_stock:
            try:
                # Recalculer le taux réel
                nouveau_taux = get_real_tax_rate_for_stock_item(mouvement.code_produit)
                
                if nouveau_taux and nouveau_taux != mouvement.taux_gnr:
                    nouveau_montant = mouvement.quantite * nouveau_taux
                    
                    # Mettre à jour le mouvement
                    frappe.db.set_value("Mouvement GNR", mouvement.name, {
                        "taux_gnr": nouveau_taux,
                        "montant_taxe_gnr": nouveau_montant
                    })
                    
                    corriges += 1
                    frappe.logger().info(f"[GNR] Mouvement stock {mouvement.name} corrigé: {mouvement.taux_gnr} → {nouveau_taux}€/L")
                
            except Exception as e:
                frappe.log_error(f"Erreur correction mouvement stock {mouvement.name}: {str(e)}")
                echecs += 1
        
        frappe.db.commit()
        
        return {
            "success": True,
            "corriges": corriges,
            "echecs": echecs,
            "message": f"{corriges} mouvements de stock corrigés avec vrais taux, {echecs} échecs",
            "total_traites": len(mouvements_stock)
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur recalcul taux mouvements stock: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def analyser_taux_stock_vs_factures():
    """
    Compare les taux GNR entre les mouvements de stock et les factures
    """
    try:
        # Analyser les taux par article selon la source
        analyse = frappe.db.sql("""
            SELECT 
                m.code_produit,
                i.item_name,
                COUNT(CASE WHEN m.reference_document = 'Stock Entry' THEN 1 END) as nb_stock,
                COUNT(CASE WHEN m.reference_document IN ('Sales Invoice', 'Purchase Invoice') THEN 1 END) as nb_factures,
                AVG(CASE WHEN m.reference_document = 'Stock Entry' THEN m.taux_gnr END) as taux_moyen_stock,
                AVG(CASE WHEN m.reference_document IN ('Sales Invoice', 'Purchase Invoice') THEN m.taux_gnr END) as taux_moyen_factures,
                MIN(m.taux_gnr) as taux_min,
                MAX(m.taux_gnr) as taux_max,
                COUNT(CASE WHEN m.taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as nb_taux_suspects
            FROM `tabMouvement GNR` m
            LEFT JOIN `tabItem` i ON m.code_produit = i.name
            WHERE m.docstatus = 1
            AND m.taux_gnr > 0
            GROUP BY m.code_produit, i.item_name
            HAVING (nb_stock > 0 OR nb_factures > 0)
            ORDER BY nb_stock + nb_factures DESC
            LIMIT 20
        """, as_dict=True)
        
        return {
            "success": True,
            "analyse_par_article": analyse,
            "resume": {
                "articles_analyses": len(analyse),
                "avec_mouvements_stock": len([a for a in analyse if a.nb_stock > 0]),
                "avec_mouvements_factures": len([a for a in analyse if a.nb_factures > 0]),
                "avec_taux_suspects": len([a for a in analyse if a.nb_taux_suspects > 0])
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur analyse taux stock vs factures: {str(e)}")
        return {"success": False, "error": str(e)}