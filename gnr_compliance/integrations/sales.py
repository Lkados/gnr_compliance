import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from datetime import datetime, timedelta

# Groupe d'articles GNR officiel
GNR_ITEM_GROUP = "Combustibles/Carburants/GNR"


def capture_vente_gnr(doc, method):
	"""
	Capture automatique des ventes GNR avec récupération du prix unitaire
	"""
	try:
		if doc.doctype != "Sales Invoice" or doc.docstatus != 1:
			return

		for item in doc.items:
			if is_gnr_product_by_group(item.item_code):
				# Le taux GNR = prix unitaire de l'article dans la facture
				prix_unitaire = get_price_from_invoice_item(item)
				
				# Créer le mouvement GNR avec le prix réel
				create_gnr_movement_from_sale(doc, item, prix_unitaire)
				
	except Exception as e:
		frappe.log_error(f"Erreur capture vente GNR: {str(e)}", "GNR Sales Capture")


def capture_achat_gnr(doc, method):
	"""
	Capture automatique des achats GNR avec récupération du prix unitaire
	"""
	try:
		if doc.doctype != "Purchase Invoice" or doc.docstatus != 1:
			return

		for item in doc.items:
			if is_gnr_product_by_group(item.item_code):
				# Le taux GNR = prix unitaire de l'article dans la facture d'achat
				prix_unitaire = get_price_from_invoice_item(item)
				
				# Créer le mouvement GNR avec le prix réel
				create_gnr_movement_from_purchase(doc, item, prix_unitaire)
				
	except Exception as e:
		frappe.log_error(f"Erreur capture achat GNR: {str(e)}", "GNR Purchase Capture")


def is_gnr_product_by_group(item_code):
	"""
	Détermine si un article est GNR UNIQUEMENT par son groupe d'articles
	"""
	if not item_code:
		return False
	
	try:
		item_group = frappe.get_value("Item", item_code, "item_group")
		is_gnr = item_group == GNR_ITEM_GROUP
		
		if is_gnr:
			frappe.logger().info(f"[GNR] Article détecté: {item_code} (groupe: {item_group})")
		else:
			frappe.logger().debug(f"[GNR] Article ignoré: {item_code} (groupe: {item_group})")
		
		return is_gnr
		
	except Exception as e:
		frappe.log_error(f"Erreur vérification groupe article {item_code}: {str(e)}")
		return False


def get_price_from_invoice_item(item):
	"""
	Récupère le prix unitaire depuis un item de facture
	PRIORITÉ: 1.Prix unitaire direct → 2.Champ personnalisé → 3.Historique → 4.ÉCHEC
	"""
	try:
		# 1. PRIORITÉ 1: Prix unitaire direct de la facture (rate)
		if item.rate and item.rate > 0:
			# Convertir en prix par litre si nécessaire
			prix_par_litre = convert_price_to_per_litre(item.rate, item.uom)
			if is_valid_price(prix_par_litre):
				frappe.logger().info(f"[GNR] Prix depuis facture: {prix_par_litre}€/L pour {item.item_code}")
				return prix_par_litre
		
		# 2. PRIORITÉ 2: Champ personnalisé prix GNR
		if hasattr(item, 'custom_prix_gnr_par_litre') and item.custom_prix_gnr_par_litre:
			if is_valid_price(item.custom_prix_gnr_par_litre):
				frappe.logger().info(f"[GNR] Prix depuis champ personnalisé: {item.custom_prix_gnr_par_litre}€/L")
				return item.custom_prix_gnr_par_litre
		
		# 3. PRIORITÉ 3: Historique récent des prix pour cet article
		historical_price = get_recent_item_price(item.item_code)
		if historical_price and is_valid_price(historical_price):
			frappe.logger().info(f"[GNR] Prix historique utilisé: {historical_price}€/L pour {item.item_code}")
			return historical_price
		
		# 4. ÉCHEC: Aucun prix trouvé
		frappe.logger().error(f"[GNR] AUCUN PRIX trouvé pour {item.item_code} - Retour 0")
		return 0.0

	except Exception as e:
		frappe.log_error(f"Erreur récupération prix item: {str(e)}")
		return 0.0


def convert_price_to_per_litre(price, uom):
	"""
	Convertit un prix selon l'UOM vers un prix par litre
	"""
	if not uom or not price:
		return price
	
	try:
		uom_lower = uom.lower().strip()
		
		# Déjà en prix par litre
		if any(unit in uom_lower for unit in ['litre', 'liter', 'l', 'lt']):
			return flt(price, 3)
		
		# Conversions courantes vers prix par litre
		conversion_factors = {
			# Prix par m³ → prix par litre
			'm3': 0.001,
			'mètre cube': 0.001,
			'cubic meter': 0.001,
			
			# Prix par hectolitre → prix par litre
			'hectolitre': 0.01,
			'hl': 0.01,
			
			# Prix par gallon → prix par litre
			'gallon': 0.264172,
			'gal': 0.264172,
		}
		
		# Recherche directe
		if uom_lower in conversion_factors:
			return flt(price * conversion_factors[uom_lower], 3)
		
		# Recherche partielle
		for unit, factor in conversion_factors.items():
			if unit in uom_lower:
				return flt(price * factor, 3)
		
		# Si aucune conversion, considérer comme prix par litre
		frappe.logger().warning(f"[GNR] UOM non reconnue: {uom}, prix considéré comme €/L")
		return flt(price, 3)
		
	except Exception as e:
		frappe.log_error(f"Erreur conversion prix UOM {uom}: {str(e)}")
		return flt(price, 3)


def get_recent_item_price(item_code, days=30):
	"""
	Récupère le prix récent moyen pour un article spécifique
	"""
	try:
		date_limit = getdate(nowdate()) - timedelta(days=days)
		
		# Récupérer les prix récents (excluant le prix 0)
		result = frappe.db.sql("""
			SELECT taux_gnr as prix, date_mouvement
			FROM `tabMouvement GNR`
			WHERE code_produit = %s 
			AND taux_gnr > 0.1 AND taux_gnr < 1000
			AND docstatus = 1
			AND date_mouvement >= %s
			ORDER BY date_mouvement DESC
			LIMIT 5
		""", (item_code, date_limit), as_dict=True)
		
		if not result:
			return None
		
		# Moyenne pondérée (plus récent = plus de poids)
		total_weight = 0
		weighted_sum = 0
		
		for i, row in enumerate(result):
			weight = len(result) - i  # Plus récent = poids plus élevé
			weighted_sum += row.prix * weight
			total_weight += weight
		
		if total_weight > 0:
			average_price = weighted_sum / total_weight
			frappe.logger().info(f"[GNR] Prix historique calculé pour {item_code}: {average_price:.3f}€/L")
			return flt(average_price, 3)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération prix historique: {str(e)}")
		return None


def is_valid_price(price):
	"""
	Vérifie si un prix GNR est valide et réaliste
	"""
	try:
		price = flt(price, 3)
		# Fourchette réaliste pour les prix GNR en France (0.10€ à 10€ par litre)
		return 0.10 <= price <= 10.0
	except:
		return False


def convert_to_litres(quantity, uom):
	"""
	Convertit une quantité vers les litres selon l'UOM
	"""
	if not uom or not quantity:
		return quantity
	
	try:
		uom_lower = uom.lower().strip()
		
		# Déjà en litres
		if any(unit in uom_lower for unit in ['litre', 'liter', 'l', 'lt']):
			return flt(quantity, 3)
		
		# Conversions courantes
		conversion_factors = {
			'm3': 1000, 'mètre cube': 1000, 'cubic meter': 1000,
			'dm3': 1, 'hectolitre': 100, 'hl': 100,
			'gallon': 3.78541, 'gal': 3.78541,
		}
		
		# Recherche directe
		if uom_lower in conversion_factors:
			return flt(quantity * conversion_factors[uom_lower], 3)
		
		# Recherche partielle
		for unit, factor in conversion_factors.items():
			if unit in uom_lower:
				return flt(quantity * factor, 3)
		
		# Par défaut, considérer comme litres
		return flt(quantity, 3)
		
	except Exception as e:
		frappe.log_error(f"Erreur conversion quantité UOM {uom}: {str(e)}")
		return flt(quantity, 3)


def create_gnr_movement_from_sale(invoice_doc, item, prix_unitaire):
	"""
	Crée un mouvement GNR depuis une vente avec le prix réel
	"""
	try:
		if prix_unitaire <= 0:
			frappe.logger().warning(f"[GNR] Mouvement non créé pour {item.item_code} - Prix invalide: {prix_unitaire}")
			return

		quantity_litres = convert_to_litres(item.qty, item.uom)
		montant_total = flt(quantity_litres * prix_unitaire, 2)
		
		mouvement_gnr = frappe.get_doc({
			"doctype": "Mouvement GNR",
			"type_mouvement": "Vente",
			"date_mouvement": getdate(invoice_doc.posting_date),
			"reference_document": "Sales Invoice",
			"reference_name": invoice_doc.name,
			"code_produit": item.item_code,
			"nom_produit": item.item_name,
			"quantite": quantity_litres,
			"unite": "Litre",
			"taux_gnr": prix_unitaire,  # Le "taux" = prix unitaire
			"montant_taxe_gnr": montant_total,  # Montant total = quantité × prix
			"prix_unitaire": prix_unitaire,
			"client": invoice_doc.customer,
			"notes": f"Mouvement automatique depuis facture {invoice_doc.name} - Prix: {prix_unitaire}€/L"
		})
		
		mouvement_gnr.insert()
		mouvement_gnr.submit()
		
		frappe.logger().info(f"[GNR] Mouvement créé: {mouvement_gnr.name} - Prix RÉEL: {prix_unitaire}€/L")
		
	except Exception as e:
		frappe.log_error(f"Erreur création mouvement GNR vente: {str(e)}")


def create_gnr_movement_from_purchase(invoice_doc, item, prix_unitaire):
	"""
	Crée un mouvement GNR depuis un achat avec le prix réel
	"""
	try:
		if prix_unitaire <= 0:
			frappe.logger().warning(f"[GNR] Mouvement achat non créé pour {item.item_code} - Prix invalide: {prix_unitaire}")
			return

		quantity_litres = convert_to_litres(item.qty, item.uom)
		montant_total = flt(quantity_litres * prix_unitaire, 2)
		
		mouvement_gnr = frappe.get_doc({
			"doctype": "Mouvement GNR",
			"type_mouvement": "Achat",
			"date_mouvement": getdate(invoice_doc.posting_date),
			"reference_document": "Purchase Invoice",
			"reference_name": invoice_doc.name,
			"code_produit": item.item_code,
			"nom_produit": item.item_name,
			"quantite": quantity_litres,
			"unite": "Litre",
			"taux_gnr": prix_unitaire,  # Le "taux" = prix unitaire
			"montant_taxe_gnr": montant_total,  # Montant total = quantité × prix
			"prix_unitaire": prix_unitaire,
			"fournisseur": invoice_doc.supplier,
			"notes": f"Mouvement automatique depuis facture achat {invoice_doc.name} - Prix: {prix_unitaire}€/L"
		})
		
		mouvement_gnr.insert()
		mouvement_gnr.submit()
		
		frappe.logger().info(f"[GNR] Mouvement achat créé: {mouvement_gnr.name} - Prix RÉEL: {prix_unitaire}€/L")
		
	except Exception as e:
		frappe.log_error(f"Erreur création mouvement GNR achat: {str(e)}")


@frappe.whitelist()
def tester_extraction_prix_facture(invoice_type, invoice_name, item_code):
	"""
	Teste l'extraction du prix pour un article spécifique dans une facture
	"""
	try:
		# Récupérer la facture
		invoice = frappe.get_doc(invoice_type, invoice_name)
		
		# Trouver l'item
		target_item = None
		for item in invoice.items:
			if item.item_code == item_code:
				target_item = item
				break
		
		if not target_item:
			return {
				"success": False,
				"message": f"Article {item_code} non trouvé dans la facture {invoice_name}"
			}
		
		# Tester l'extraction du prix
		prix_unitaire = get_price_from_invoice_item(target_item)
		
		# Informations détaillées
		details = {
			"item_code": item_code,
			"item_name": target_item.item_name,
			"quantity": target_item.qty,
			"uom": target_item.uom,
			"rate_facture": target_item.rate,
			"prix_par_litre_calcule": prix_unitaire,
			"quantity_en_litres": convert_to_litres(target_item.qty, target_item.uom),
			"montant_total": flt(convert_to_litres(target_item.qty, target_item.uom) * prix_unitaire, 2),
			"groupe_article": frappe.get_value("Item", item_code, "item_group"),
			"est_gnr": is_gnr_product_by_group(item_code)
		}
		
		return {
			"success": True,
			"prix_unitaire": prix_unitaire,
			"details": details,
			"message": f"Prix extrait: {prix_unitaire}€/L pour {item_code}"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur test extraction prix: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def analyser_prix_factures_recentes(limite=20):
	"""
	Analyse les prix dans les factures récentes
	"""
	try:
		# Factures de vente récentes avec articles GNR
		factures = frappe.db.sql("""
			SELECT DISTINCT
				si.name,
				si.posting_date,
				si.customer,
				sii.item_code,
				i.item_name,
				sii.qty,
				sii.uom,
				sii.rate,
				sii.amount
			FROM `tabSales Invoice` si
			JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
			JOIN `tabItem` i ON sii.item_code = i.name
			WHERE si.docstatus = 1
			AND i.item_group = %s
			AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			ORDER BY si.posting_date DESC
			LIMIT %s
		""", (GNR_ITEM_GROUP, limite), as_dict=True)
		
		analyses = []
		for facture in factures:
			# Calculer prix par litre
			quantity_litres = convert_to_litres(facture.qty, facture.uom)
			prix_par_litre = facture.rate
			
			if facture.uom and facture.uom.lower() not in ['litre', 'l', 'liter']:
				prix_par_litre = convert_price_to_per_litre(facture.rate, facture.uom)
			
			# Vérifier s'il y a un mouvement GNR correspondant
			mouvement_existe = frappe.db.exists("Mouvement GNR", {
				"reference_document": "Sales Invoice",
				"reference_name": facture.name,
				"code_produit": facture.item_code,
				"docstatus": 1
			})
			
			analyses.append({
				"facture": facture.name,
				"date": facture.posting_date,
				"client": facture.customer,
				"article": facture.item_code,
				"nom_article": facture.item_name,
				"quantite": facture.qty,
				"uom": facture.uom,
				"prix_facture": facture.rate,
				"prix_par_litre": prix_par_litre,
				"montant_total": facture.amount,
				"mouvement_gnr_cree": "✅" if mouvement_existe else "❌",
				"prix_valide": "✅" if is_valid_price(prix_par_litre) else "❌"
			})
		
		# Statistiques
		total_factures = len(analyses)
		avec_mouvements = len([a for a in analyses if a["mouvement_gnr_cree"] == "✅"])
		prix_valides = len([a for a in analyses if a["prix_valide"] == "✅"])
		
		return {
			"success": True,
			"total_factures": total_factures,
			"avec_mouvements_gnr": avec_mouvements,
			"prix_valides": prix_valides,
			"taux_couverture": f"{(avec_mouvements/total_factures*100):.1f}%" if total_factures > 0 else "0%",
			"analyses": analyses,
			"message": f"Analysé {total_factures} factures - {avec_mouvements} avec mouvements GNR"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur analyse prix factures: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def creer_champ_prix_gnr_personnalise():
	"""
	Crée un champ personnalisé pour forcer le prix GNR par litre si nécessaire
	"""
	try:
		# Champ dans Sales Invoice Item
		if not frappe.db.exists("Custom Field", "Sales Invoice Item-custom_prix_gnr_par_litre"):
			custom_field = frappe.get_doc({
				"doctype": "Custom Field",
				"dt": "Sales Invoice Item",
				"fieldname": "custom_prix_gnr_par_litre",
				"label": "Prix GNR (€/L)",
				"fieldtype": "Currency",
				"insert_after": "rate",
				"description": "Prix GNR forcé en €/L (optionnel - laissez vide pour utiliser le prix automatique)"
			})
			custom_field.insert()
			print("✅ Champ 'custom_prix_gnr_par_litre' créé pour Sales Invoice Item")
		
		# Champ dans Purchase Invoice Item
		if not frappe.db.exists("Custom Field", "Purchase Invoice Item-custom_prix_gnr_par_litre"):
			custom_field = frappe.get_doc({
				"doctype": "Custom Field",
				"dt": "Purchase Invoice Item",
				"fieldname": "custom_prix_gnr_par_litre",
				"label": "Prix GNR (€/L)",
				"fieldtype": "Currency",
				"insert_after": "rate",
				"description": "Prix GNR forcé en €/L (optionnel - laissez vide pour utiliser le prix automatique)"
			})
			custom_field.insert()
			print("✅ Champ 'custom_prix_gnr_par_litre' créé pour Purchase Invoice Item")
		
		return {
			"success": True,
			"message": "Champs personnalisés pour prix GNR créés avec succès"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur création champs prix GNR: {str(e)}")
		return {"success": False, "error": str(e)}