import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
import re
from datetime import datetime, timedelta

# Groupe d'articles GNR officiel
GNR_ITEM_GROUP = "Combustibles/Carburants/GNR"


def get_dynamic_gnr_rate_for_item(item_code, source_document=None, source_name=None):
	"""
	Fonction principale pour récupérer le taux GNR dynamiquement (SANS valeurs par défaut)
	PRIORITÉ: 1.Document source → 2.Historique récent → 3.ÉCHEC (taux 0)
	"""
	try:
		if not item_code:
			frappe.logger().error("[GNR] Code article manquant")
			return 0.0
		
		# Vérifier que l'article est dans le bon groupe
		if not is_item_in_gnr_group(item_code):
			frappe.logger().debug(f"[GNR] Article {item_code} pas dans groupe GNR")
			return 0.0
		
		# 1. PRIORITÉ 1: Depuis le document source si fourni
		if source_document and source_name:
			source_rate = extract_rate_from_source_document(item_code, source_document, source_name)
			if source_rate and is_valid_rate(source_rate):
				log_rate_source(item_code, source_rate, f"Document {source_document} {source_name}")
				return source_rate
		
		# 2. PRIORITÉ 2: Historique récent de cet article (30 derniers jours)
		historical_rate = get_recent_item_rate(item_code, days=30)
		if historical_rate and is_valid_rate(historical_rate):
			log_rate_source(item_code, historical_rate, "Historique récent (30j)")
			return historical_rate
		
		# 3. PRIORITÉ 3: Historique étendu (90 jours)
		extended_rate = get_recent_item_rate(item_code, days=90)
		if extended_rate and is_valid_rate(extended_rate):
			log_rate_source(item_code, extended_rate, "Historique étendu (90j)")
			return extended_rate
		
		# 4. ÉCHEC: Aucun taux trouvé
		frappe.logger().warning(f"[GNR] AUCUN TAUX TROUVÉ pour {item_code} - Retour 0")
		return 0.0
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux dynamique pour {item_code}: {str(e)}")
		return 0.0


def is_item_in_gnr_group(item_code):
	"""
	Vérifie si un article est dans le groupe GNR officiel
	"""
	try:
		item_group = frappe.get_value("Item", item_code, "item_group")
		return item_group == GNR_ITEM_GROUP
	except:
		return False


def extract_rate_from_source_document(item_code, doc_type, doc_name):
	"""
	Extrait le taux depuis un document source (facture, etc.)
	"""
	try:
		if doc_type in ["Sales Invoice", "Purchase Invoice"]:
			return extract_rate_from_invoice(item_code, doc_type, doc_name)
		elif doc_type == "Stock Entry":
			return extract_rate_from_stock_entry(item_code, doc_name)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur extraction taux document {doc_type} {doc_name}: {str(e)}")
		return None


def extract_rate_from_invoice(item_code, doc_type, doc_name):
	"""
	Extrait le taux GNR depuis une facture
	"""
	try:
		invoice = frappe.get_doc(doc_type, doc_name)
		
		# Trouver l'item dans la facture
		target_item = None
		for item in invoice.items:
			if item.item_code == item_code:
				target_item = item
				break
		
		if not target_item:
			return None
		
		# 1. Champ personnalisé dans l'item
		if hasattr(target_item, 'custom_taux_gnr') and target_item.custom_taux_gnr:
			if is_valid_rate(target_item.custom_taux_gnr):
				frappe.logger().info(f"[GNR] Taux depuis champ personnalisé: {target_item.custom_taux_gnr}€/L")
				return target_item.custom_taux_gnr
		
		# 2. Analyser les taxes de la facture
		if hasattr(invoice, 'taxes') and invoice.taxes:
			quantity_in_litres = convert_to_litres(target_item.qty, target_item.uom)
			
			if quantity_in_litres > 0:
				for tax_row in invoice.taxes:
					if tax_row.description:
						description_lower = tax_row.description.lower()
						gnr_keywords = [
							'gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant', 
							'diesel', 'combustible', 'taxe intérieure', 'tipp'
						]
						
						if any(keyword in description_lower for keyword in gnr_keywords):
							if tax_row.tax_amount and tax_row.tax_amount != 0:
								taux_calcule = abs(tax_row.tax_amount) / quantity_in_litres
								
								if is_valid_rate(taux_calcule):
									frappe.logger().info(f"[GNR] Taux calculé depuis taxe '{tax_row.description}': {taux_calcule}€/L")
									return taux_calcule
		
		# 3. Essayer de déduire depuis le montant total si possible
		return deduce_rate_from_item_totals(target_item, invoice)
		
	except Exception as e:
		frappe.log_error(f"Erreur extraction taux facture {doc_name}: {str(e)}")
		return None


def deduce_rate_from_item_totals(item, invoice):
	"""
	Essaie de déduire le taux GNR depuis les montants de l'item
	"""
	try:
		# Si l'item a un champ montant_taxe_gnr personnalisé
		if hasattr(item, 'custom_montant_taxe_gnr') and item.custom_montant_taxe_gnr:
			quantity_in_litres = convert_to_litres(item.qty, item.uom)
			if quantity_in_litres > 0:
				taux_deduit = abs(item.custom_montant_taxe_gnr) / quantity_in_litres
				if is_valid_rate(taux_deduit):
					frappe.logger().info(f"[GNR] Taux déduit depuis montant taxe: {taux_deduit}€/L")
					return taux_deduit
		
		# Analyser les écarts de prix si pattern reconnaissable
		if item.rate and item.base_rate and item.rate != item.base_rate:
			quantity_in_litres = convert_to_litres(item.qty, item.uom)
			if quantity_in_litres > 0:
				ecart_prix = abs(item.rate - item.base_rate)
				taux_potentiel = ecart_prix / quantity_in_litres
				
				# Seulement si dans une fourchette réaliste
				if 0.5 <= taux_potentiel <= 50:
					frappe.logger().info(f"[GNR] Taux potentiel depuis écart prix: {taux_potentiel}€/L")
					return taux_potentiel
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur déduction taux: {str(e)}")
		return None


def extract_rate_from_stock_entry(item_code, doc_name):
	"""
	Extrait le taux depuis une entrée de stock (lien facture d'achat)
	"""
	try:
		stock_entry = frappe.get_doc("Stock Entry", doc_name)
		
		# Chercher une facture d'achat liée
		if hasattr(stock_entry, 'purchase_receipt') and stock_entry.purchase_receipt:
			pr = frappe.get_doc("Purchase Receipt", stock_entry.purchase_receipt)
			
			# Chercher par numéro de facture
			if hasattr(pr, 'bill_no') and pr.bill_no:
				purchase_invoices = frappe.get_all("Purchase Invoice",
					filters={
						"bill_no": pr.bill_no,
						"supplier": pr.supplier,
						"docstatus": 1
					},
					limit=1
				)
				
				if purchase_invoices:
					return extract_rate_from_invoice(item_code, "Purchase Invoice", purchase_invoices[0].name)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur extraction taux stock entry: {str(e)}")
		return None


def get_recent_item_rate(item_code, days=30):
	"""
	Récupère le taux récent moyen pour un article spécifique
	"""
	try:
		date_limit = getdate(nowdate()) - timedelta(days=days)
		
		# Récupérer les taux récents (excluant le taux 0)
		result = frappe.db.sql("""
			SELECT taux_gnr, date_mouvement, montant_taxe_gnr, quantite
			FROM `tabMouvement GNR`
			WHERE code_produit = %s 
			AND taux_gnr > 0.1 AND taux_gnr < 100
			AND docstatus = 1
			AND date_mouvement >= %s
			ORDER BY date_mouvement DESC
			LIMIT 10
		""", (item_code, date_limit), as_dict=True)
		
		if not result:
			return None
		
		# Filtrer les taux cohérents (vérifier calcul montant_taxe = quantite * taux)
		taux_coherents = []
		for row in result:
			montant_attendu = row.quantite * row.taux_gnr
			ecart = abs(montant_attendu - (row.montant_taxe_gnr or 0))
			
			# Accepter si écart < 5% ou < 0.10€
			if ecart < max(montant_attendu * 0.05, 0.10):
				taux_coherents.append(row.taux_gnr)
		
		if taux_coherents:
			# Moyenne pondérée (plus récent = plus de poids)
			total_weight = 0
			weighted_sum = 0
			
			for i, taux in enumerate(taux_coherents):
				weight = len(taux_coherents) - i  # Plus récent = poids plus élevé
				weighted_sum += taux * weight
				total_weight += weight
			
			if total_weight > 0:
				average_rate = weighted_sum / total_weight
				frappe.logger().info(f"[GNR] Taux historique calculé pour {item_code}: {average_rate:.3f}€/L (basé sur {len(taux_coherents)} mouvements)")
				return flt(average_rate, 3)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux historique: {str(e)}")
		return None


def is_valid_rate(rate):
	"""
	Vérifie si un taux GNR est valide et réaliste
	"""
	try:
		rate = flt(rate, 3)
		# Fourchette réaliste pour les taux GNR en France
		return 0.01 <= rate <= 100.0
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
			'dm3': 1, 'decimeter cube': 1,
			'cm3': 0.001, 'millilitre': 0.001, 'ml': 0.001,
			'hectolitre': 100, 'hl': 100,
			'décalitre': 10, 'dal': 10,
			'centilitre': 0.01, 'cl': 0.01,
			'gallon': 3.78541, 'gal': 3.78541,
			'quart': 0.946353, 'pint': 0.473176
		}
		
		# Recherche directe
		if uom_lower in conversion_factors:
			return flt(quantity * conversion_factors[uom_lower], 3)
		
		# Recherche partielle
		for unit, factor in conversion_factors.items():
			if unit in uom_lower:
				return flt(quantity * factor, 3)
		
		# Si aucune conversion trouvée, considérer comme litres
		frappe.logger().warning(f"[GNR] UOM non reconnue: {uom}, considéré comme litres")
		return flt(quantity, 3)
		
	except Exception as e:
		frappe.log_error(f"Erreur conversion UOM {uom}: {str(e)}")
		return flt(quantity, 3)


def log_rate_source(item_code, rate, source):
	"""
	Log la source du taux pour traçabilité
	"""
	try:
		frappe.logger().info(f"[GNR] {item_code}: Taux {rate}€/L depuis {source}")
	except:
		pass


@frappe.whitelist()
def analyser_taux_disponibles_periode(from_date=None, to_date=None):
	"""
	Analyse les taux GNR disponibles sur une période
	"""
	try:
		conditions = ["m.docstatus = 1", "m.taux_gnr > 0.1"]
		values = []
		
		if from_date:
			conditions.append("m.date_mouvement >= %s")
			values.append(from_date)
		
		if to_date:
			conditions.append("m.date_mouvement <= %s")
			values.append(to_date)
		
		where_clause = " AND ".join(conditions)
		
		# Analyser les taux par article
		result = frappe.db.sql(f"""
			SELECT 
				m.code_produit,
				i.item_name,
				i.item_group,
				COUNT(*) as nb_mouvements,
				AVG(m.taux_gnr) as taux_moyen,
				MIN(m.taux_gnr) as taux_min,
				MAX(m.taux_gnr) as taux_max,
				STDDEV(m.taux_gnr) as ecart_type,
				SUM(m.quantite) as quantite_totale,
				-- Vérifier la cohérence des calculs
				COUNT(CASE 
					WHEN ABS(m.montant_taxe_gnr - (m.quantite * m.taux_gnr)) < 0.10 
					THEN 1 
				END) as calculs_coherents
			FROM `tabMouvement GNR` m
			LEFT JOIN `tabItem` i ON m.code_produit = i.name
			WHERE {where_clause}
			GROUP BY m.code_produit, i.item_name, i.item_group
			HAVING nb_mouvements >= 1
			ORDER BY quantite_totale DESC
		""", values, as_dict=True)
		
		# Statistiques globales
		articles_gnr_groupe = [r for r in result if r.item_group == GNR_ITEM_GROUP]
		articles_autres_groupes = [r for r in result if r.item_group != GNR_ITEM_GROUP]
		
		# Analyser la qualité des taux
		articles_bonne_qualite = [r for r in result if r.ecart_type and r.ecart_type < 1.0]
		articles_taux_variables = [r for r in result if r.ecart_type and r.ecart_type >= 5.0]
		
		return {
			"success": True,
			"periode": f"{from_date or 'Début'} au {to_date or 'Fin'}",
			"total_articles": len(result),
			"articles_groupe_gnr": len(articles_gnr_groupe),
			"articles_autres_groupes": len(articles_autres_groupes),
			"articles_bonne_qualite": len(articles_bonne_qualite),
			"articles_taux_variables": len(articles_taux_variables),
			"details_articles": result[:20],  # Limiter pour l'affichage
			"recommandations": generer_recommandations_taux(result)
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur analyse taux période: {str(e)}")
		return {"success": False, "error": str(e)}


def generer_recommandations_taux(articles_data):
	"""
	Génère des recommandations basées sur l'analyse des taux
	"""
	recommendations = []
	
	# Articles avec taux très variables
	variables = [a for a in articles_data if a.ecart_type and a.ecart_type > 5.0]
	if variables:
		recommendations.append({
			"type": "warning",
			"message": f"{len(variables)} article(s) ont des taux très variables (écart-type > 5€). Vérifiez la cohérence.",
			"articles": [f"{a.code_produit} (écart: {a.ecart_type:.2f})" for a in variables[:3]]
		})
	
	# Articles pas dans le groupe GNR
	hors_groupe = [a for a in articles_data if a.item_group != GNR_ITEM_GROUP]
	if hors_groupe:
		recommendations.append({
			"type": "info",
			"message": f"{len(hors_groupe)} article(s) avec mouvements GNR ne sont pas dans le groupe '{GNR_ITEM_GROUP}'.",
			"articles": [f"{a.code_produit} (groupe: {a.item_group})" for a in hors_groupe[:3]]
		})
	
	# Articles avec calculs incohérents
	incoherents = [a for a in articles_data if a.calculs_coherents < a.nb_mouvements * 0.8]
	if incoherents:
		recommendations.append({
			"type": "error",
			"message": f"{len(incoherents)} article(s) ont des calculs de taxe incohérents.",
			"articles": [f"{a.code_produit} ({a.calculs_coherents}/{a.nb_mouvements} cohérents)" for a in incoherents[:3]]
		})
	
	if not recommendations:
		recommendations.append({
			"type": "success",
			"message": "✅ Tous les taux semblent cohérents et bien configurés!"
		})
	
	return recommendations


@frappe.whitelist()
def detecter_articles_sans_taux():
	"""
	Détecte les articles GNR qui n'ont jamais eu de taux valide
	"""
	try:
		# Articles dans le groupe GNR
		articles_gnr = frappe.get_all("Item",
			filters={"item_group": GNR_ITEM_GROUP},
			fields=["name", "item_name"]
		)
		
		articles_sans_taux = []
		
		for article in articles_gnr:
			# Vérifier s'il y a des mouvements avec taux valide
			mouvements_avec_taux = frappe.db.count("Mouvement GNR", {
				"code_produit": article.name,
				"taux_gnr": [">", 0.1],
				"docstatus": 1
			})
			
			if mouvements_avec_taux == 0:
				# Vérifier s'il y a des mouvements du tout
				total_mouvements = frappe.db.count("Mouvement GNR", {
					"code_produit": article.name,
					"docstatus": 1
				})
				
				articles_sans_taux.append({
					"code_produit": article.name,
					"item_name": article.item_name,
					"total_mouvements": total_mouvements
				})
		
		return {
			"success": True,
			"total_articles_gnr": len(articles_gnr),
			"articles_sans_taux": articles_sans_taux,
			"nb_sans_taux": len(articles_sans_taux),
			"message": f"{len(articles_sans_taux)} article(s) GNR sans taux valide trouvé(s)"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur détection articles sans taux: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def recalculer_avec_taux_dynamiques(limite=50):
	"""
	Recalcule les mouvements en utilisant la logique dynamique
	"""
	try:
		# Récupérer les mouvements avec taux zéro ou suspects
		mouvements = frappe.db.sql("""
			SELECT name, code_produit, reference_document, reference_name, quantite, taux_gnr
			FROM `tabMouvement GNR`
			WHERE docstatus = 1
			AND (taux_gnr = 0 OR taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81))
			ORDER BY creation DESC
			LIMIT %s
		""", (limite,), as_dict=True)
		
		corriges = 0
		echecs = 0
		ameliorations = []
		
		for mouvement in mouvements:
			try:
				# Recalculer avec la logique dynamique
				nouveau_taux = get_dynamic_gnr_rate_for_item(
					mouvement.code_produit,
					mouvement.reference_document,
					mouvement.reference_name
				)
				
				if nouveau_taux > 0 and nouveau_taux != mouvement.taux_gnr:
					# Mettre à jour
					nouveau_montant = flt(mouvement.quantite * nouveau_taux, 2)
					
					frappe.db.set_value("Mouvement GNR", mouvement.name, {
						"taux_gnr": nouveau_taux,
						"montant_taxe_gnr": nouveau_montant
					})
					
					ameliorations.append({
						"mouvement": mouvement.name,
						"code_produit": mouvement.code_produit,
						"ancien_taux": mouvement.taux_gnr,
						"nouveau_taux": nouveau_taux
					})
					
					corriges += 1
				else:
					echecs += 1
			
			except Exception as e:
				frappe.log_error(f"Erreur recalcul mouvement {mouvement.name}: {str(e)}")
				echecs += 1
		
		frappe.db.commit()
		
		return {
			"success": True,
			"total_traites": len(mouvements),
			"corriges": corriges,
			"echecs": echecs,
			"ameliorations": ameliorations[:10],
			"message": f"{corriges} mouvements recalculés avec logique dynamique"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur recalcul dynamique: {str(e)}")
		return {"success": False, "error": str(e)}