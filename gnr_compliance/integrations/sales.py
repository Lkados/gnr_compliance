import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
import re


def capture_vente_gnr(doc, method):
	"""
	Capture automatique des ventes GNR avec détection par groupe d'articles
	"""
	try:
		if doc.doctype != "Sales Invoice" or doc.docstatus != 1:
			return

		for item in doc.items:
			if is_gnr_product_by_group(item.item_code):
				# Récupérer le vrai taux depuis cette facture
				taux_gnr_reel = get_real_gnr_tax_from_invoice(item, doc)
				
				# Créer le mouvement GNR avec le taux réel
				create_gnr_movement_from_sale(doc, item, taux_gnr_reel)
				
	except Exception as e:
		frappe.log_error(f"Erreur capture vente GNR: {str(e)}", "GNR Sales Capture")


def capture_achat_gnr(doc, method):
	"""
	Capture automatique des achats GNR avec détection par groupe d'articles
	"""
	try:
		if doc.doctype != "Purchase Invoice" or doc.docstatus != 1:
			return

		for item in doc.items:
			if is_gnr_product_by_group(item.item_code):
				# Récupérer le vrai taux depuis cette facture d'achat
				taux_gnr_reel = get_real_gnr_tax_from_purchase_invoice(item, doc)
				
				# Créer le mouvement GNR avec le taux réel
				create_gnr_movement_from_purchase(doc, item, taux_gnr_reel)
				
	except Exception as e:
		frappe.log_error(f"Erreur capture achat GNR: {str(e)}", "GNR Purchase Capture")


def is_gnr_product_by_group(item_code):
	"""
	Détermine si un article est soumis à la taxe GNR UNIQUEMENT par son groupe d'articles
	Seuls les articles dans le groupe "Combustibles/Carburants/GNR" sont considérés
	"""
	if not item_code:
		return False
	
	try:
		# Récupérer le groupe d'articles
		item_group = frappe.get_value("Item", item_code, "item_group")
		
		# Vérifier si c'est exactement le groupe GNR
		if item_group == "Combustibles/Carburants/GNR":
			return True
		
		# Log pour traçabilité des articles non détectés
		frappe.logger().debug(f"[GNR] Article {item_code} dans groupe '{item_group}' - Non GNR")
		return False
		
	except Exception as e:
		frappe.log_error(f"Erreur vérification groupe article {item_code}: {str(e)}")
		return False


def get_real_gnr_tax_from_invoice(item, invoice_doc):
	"""
	Récupère le VRAI taux GNR depuis une facture de vente
	PRIORITÉ: 1.Taxes facture → 2.Champs personnalisés item → 3.Historique → 4.ÉCHEC
	"""
	try:
		# 1. PRIORITÉ 1: Analyser les taxes réelles de la facture
		taux_depuis_taxes = extraire_taux_depuis_taxes_facture(item, invoice_doc)
		if taux_depuis_taxes and is_valid_gnr_rate(taux_depuis_taxes):
			frappe.logger().info(f"[GNR] Taux RÉEL trouvé dans taxes: {taux_depuis_taxes}€/L pour {item.item_code}")
			return taux_depuis_taxes

		# 2. PRIORITÉ 2: Champs personnalisés dans l'item de la facture
		if hasattr(item, 'custom_taux_gnr') and item.custom_taux_gnr:
			if is_valid_gnr_rate(item.custom_taux_gnr):
				frappe.logger().info(f"[GNR] Taux trouvé dans champ item facture: {item.custom_taux_gnr}€/L")
				return item.custom_taux_gnr

		# 3. PRIORITÉ 3: Historique récent de cet article spécifique
		historical_rate = get_recent_historical_rate(item.item_code)
		if historical_rate and is_valid_gnr_rate(historical_rate):
			frappe.logger().info(f"[GNR] Taux historique utilisé: {historical_rate}€/L pour {item.item_code}")
			return historical_rate

		# 4. ÉCHEC: Aucun taux trouvé
		frappe.logger().error(f"[GNR] AUCUN TAUX trouvé pour {item.item_code} dans facture {invoice_doc.name}")
		
		# Retourner 0 pour forcer une recherche manuelle du taux
		return 0.0

	except Exception as e:
		frappe.log_error(f"Erreur récupération taux réel facture: {str(e)}")
		return 0.0


def get_real_gnr_tax_from_purchase_invoice(item, invoice_doc):
	"""
	Récupère le VRAI taux GNR depuis une facture d'achat
	"""
	try:
		# 1. Analyser les taxes de la facture d'achat
		taux_depuis_taxes = extraire_taux_depuis_taxes_facture(item, invoice_doc)
		if taux_depuis_taxes and is_valid_gnr_rate(taux_depuis_taxes):
			frappe.logger().info(f"[GNR] Taux RÉEL trouvé dans taxes achat: {taux_depuis_taxes}€/L")
			return taux_depuis_taxes

		# 2. Champs personnalisés
		if hasattr(item, 'custom_taux_gnr') and item.custom_taux_gnr:
			if is_valid_gnr_rate(item.custom_taux_gnr):
				return item.custom_taux_gnr

		# 3. Historique
		historical_rate = get_recent_historical_rate(item.item_code)
		if historical_rate and is_valid_gnr_rate(historical_rate):
			return historical_rate

		# 4. Échec
		frappe.logger().error(f"[GNR] AUCUN TAUX trouvé pour achat {item.item_code}")
		return 0.0

	except Exception as e:
		frappe.log_error(f"Erreur récupération taux achat: {str(e)}")
		return 0.0


def extraire_taux_depuis_taxes_facture(item, invoice_doc):
	"""
	Extrait le taux GNR depuis les lignes de taxes de la facture
	"""
	try:
		if not hasattr(invoice_doc, 'taxes') or not invoice_doc.taxes:
			return None

		# Convertir la quantité en litres
		quantity_in_litres = convert_to_litres(item.qty, item.uom)
		
		if quantity_in_litres <= 0:
			return None

		for tax_row in invoice_doc.taxes:
			if not tax_row.description:
				continue
				
			description_lower = tax_row.description.lower()
			
			# Mots-clés pour identifier une taxe GNR
			gnr_keywords = [
				'gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant', 
				'diesel', 'combustible', 'taxe intérieure'
			]
			
			# Vérifier si c'est une taxe GNR
			if any(keyword in description_lower for keyword in gnr_keywords):
				if tax_row.tax_amount and tax_row.tax_amount != 0:
					# Calculer le taux par litre
					taux_calcule = abs(tax_row.tax_amount) / quantity_in_litres
					
					if is_valid_gnr_rate(taux_calcule):
						frappe.logger().info(f"[GNR] Taxe détectée: '{tax_row.description}' = {taux_calcule}€/L")
						return taux_calcule

		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur extraction taux depuis taxes: {str(e)}")
		return None


def get_recent_historical_rate(item_code, days=30):
	"""
	Récupère le taux historique récent pour un article spécifique
	"""
	try:
		from datetime import timedelta
		date_limite = getdate(nowdate()) - timedelta(days=days)
		
		result = frappe.db.sql("""
			SELECT taux_gnr 
			FROM `tabMouvement GNR` 
			WHERE code_produit = %s 
			AND taux_gnr > 0.1 AND taux_gnr < 100
			AND docstatus = 1 
			AND date_mouvement >= %s
			ORDER BY date_mouvement DESC 
			LIMIT 3
		""", (item_code, date_limite))
		
		if result:
			# Prendre la moyenne des 3 derniers taux
			rates = [row[0] for row in result]
			average_rate = sum(rates) / len(rates)
			return flt(average_rate, 3)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération historique: {str(e)}")
		return None


def is_valid_gnr_rate(rate):
	"""
	Vérifie si un taux GNR est valide et réaliste
	"""
	try:
		rate = flt(rate, 3)
		# Fourchette réaliste pour les taux GNR en France (0.1€ à 100€ par litre)
		return 0.1 <= rate <= 100.0
	except:
		return False


def convert_to_litres(quantity, uom):
	"""
	Convertit une quantité vers les litres selon l'UOM
	"""
	if not uom:
		return quantity
	
	uom_lower = uom.lower()
	
	# Déjà en litres
	if any(unit in uom_lower for unit in ['litre', 'liter', 'l']):
		return quantity
	
	# Conversions courantes
	conversion_factors = {
		'm3': 1000,
		'mètre cube': 1000,
		'dm3': 1,
		'cm3': 0.001,
		'hectolitre': 100,
		'hl': 100,
		'gallon': 3.78541,
		'pint': 0.473176
	}
	
	for unit, factor in conversion_factors.items():
		if unit in uom_lower:
			return quantity * factor
	
	# Par défaut, considérer comme litres
	return quantity


def create_gnr_movement_from_sale(invoice_doc, item, taux_gnr):
	"""
	Crée un mouvement GNR depuis une vente avec le taux réel
	"""
	try:
		if taux_gnr <= 0:
			frappe.logger().warning(f"[GNR] Mouvement non créé pour {item.item_code} - Taux invalide: {taux_gnr}")
			return

		quantity_litres = convert_to_litres(item.qty, item.uom)
		montant_taxe = flt(quantity_litres * taux_gnr, 2)
		
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
			"taux_gnr": taux_gnr,
			"montant_taxe_gnr": montant_taxe,
			"prix_unitaire": item.rate,
			"client": invoice_doc.customer,
			"notes": f"Mouvement automatique depuis facture {invoice_doc.name} - Taux réel: {taux_gnr}€/L"
		})
		
		mouvement_gnr.insert()
		mouvement_gnr.submit()
		
		frappe.logger().info(f"[GNR] Mouvement créé: {mouvement_gnr.name} - Taux RÉEL: {taux_gnr}€/L")
		
	except Exception as e:
		frappe.log_error(f"Erreur création mouvement GNR vente: {str(e)}")


def create_gnr_movement_from_purchase(invoice_doc, item, taux_gnr):
	"""
	Crée un mouvement GNR depuis un achat avec le taux réel
	"""
	try:
		if taux_gnr <= 0:
			frappe.logger().warning(f"[GNR] Mouvement achat non créé pour {item.item_code} - Taux invalide: {taux_gnr}")
			return

		quantity_litres = convert_to_litres(item.qty, item.uom)
		montant_taxe = flt(quantity_litres * taux_gnr, 2)
		
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
			"taux_gnr": taux_gnr,
			"montant_taxe_gnr": montant_taxe,
			"prix_unitaire": item.rate,
			"fournisseur": invoice_doc.supplier,
			"notes": f"Mouvement automatique depuis facture achat {invoice_doc.name} - Taux réel: {taux_gnr}€/L"
		})
		
		mouvement_gnr.insert()
		mouvement_gnr.submit()
		
		frappe.logger().info(f"[GNR] Mouvement achat créé: {mouvement_gnr.name} - Taux RÉEL: {taux_gnr}€/L")
		
	except Exception as e:
		frappe.log_error(f"Erreur création mouvement GNR achat: {str(e)}")


@frappe.whitelist()
def verifier_articles_gnr_par_groupe():
	"""
	Vérifie quels articles sont dans le groupe GNR et génère un rapport
	"""
	try:
		# Récupérer tous les articles du groupe GNR
		articles_gnr = frappe.get_all("Item", 
			filters={"item_group": "Combustibles/Carburants/GNR"},
			fields=["name", "item_name", "item_group", "is_gnr_tracked"]
		)
		
		# Récupérer les articles marqués GNR mais pas dans le bon groupe
		articles_mal_configures = frappe.db.sql("""
			SELECT name, item_name, item_group, is_gnr_tracked
			FROM `tabItem`
			WHERE is_gnr_tracked = 1 
			AND item_group != 'Combustibles/Carburants/GNR'
		""", as_dict=True)
		
		return {
			"success": True,
			"articles_groupe_gnr": articles_gnr,
			"articles_mal_configures": articles_mal_configures,
			"total_groupe_gnr": len(articles_gnr),
			"total_mal_configures": len(articles_mal_configures),
			"message": f"Trouvé {len(articles_gnr)} articles dans le groupe GNR et {len(articles_mal_configures)} mal configurés"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur vérification articles GNR: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def corriger_configuration_articles_gnr():
	"""
	Corrige la configuration des articles GNR selon le groupe
	"""
	try:
		# 1. Marquer tous les articles du groupe GNR comme trackés
		articles_gnr = frappe.get_all("Item", 
			filters={"item_group": "Combustibles/Carburants/GNR"},
			pluck="name"
		)
		
		for item_code in articles_gnr:
			frappe.db.set_value("Item", item_code, "is_gnr_tracked", 1)
		
		# 2. Démarquer les articles qui ne sont plus dans le groupe GNR
		frappe.db.sql("""
			UPDATE `tabItem`
			SET is_gnr_tracked = 0
			WHERE item_group != 'Combustibles/Carburants/GNR'
			AND is_gnr_tracked = 1
		""")
		
		frappe.db.commit()
		
		return {
			"success": True,
			"articles_marques": len(articles_gnr),
			"message": f"{len(articles_gnr)} articles du groupe GNR marqués comme trackés"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur correction articles GNR: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def analyser_taux_manquants(from_date=None, to_date=None):
	"""
	Analyse les mouvements où le taux GNR n'a pas pu être récupéré
	"""
	try:
		conditions = ["m.docstatus = 1", "m.taux_gnr = 0"]
		values = []
		
		if from_date:
			conditions.append("m.date_mouvement >= %s")
			values.append(from_date)
		
		if to_date:
			conditions.append("m.date_mouvement <= %s")
			values.append(to_date)
		
		where_clause = " AND ".join(conditions)
		
		mouvements_sans_taux = frappe.db.sql(f"""
			SELECT 
				m.name,
				m.code_produit,
				i.item_name,
				m.reference_document,
				m.reference_name,
				m.date_mouvement,
				m.quantite,
				i.item_group
			FROM `tabMouvement GNR` m
			LEFT JOIN `tabItem` i ON m.code_produit = i.name
			WHERE {where_clause}
			ORDER BY m.date_mouvement DESC
			LIMIT 50
		""", values, as_dict=True)
		
		return {
			"success": True,
			"mouvements_sans_taux": mouvements_sans_taux,
			"total": len(mouvements_sans_taux),
			"message": f"Trouvé {len(mouvements_sans_taux)} mouvements sans taux GNR"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur analyse taux manquants: {str(e)}")
		return {"success": False, "error": str(e)}