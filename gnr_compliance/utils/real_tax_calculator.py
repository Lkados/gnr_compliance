# -*- coding: utf-8 -*-
"""
Calculateur de taux GNR réels depuis toutes les sources
Chemin: gnr_compliance/utils/real_tax_calculator.py
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
import re
import json
from datetime import datetime, timedelta


def get_real_gnr_rate_for_item(item_code, source_document=None, source_name=None):
	"""
	Fonction principale pour récupérer le VRAI taux GNR d'un article
	PRIORITÉ: 1.Document source → 2.Article → 3.Historique → 4.Analyse nom → 5.Défaut
	"""
	try:
		if not item_code:
			return get_default_rate_by_category("GNR")
		
		# 1. PRIORITÉ 1: Depuis le document source si fourni
		if source_document and source_name:
			source_rate = get_rate_from_source_document(item_code, source_document, source_name)
			if source_rate and is_valid_rate(source_rate):
				log_rate_source(item_code, source_rate, f"Document source {source_document}")
				return source_rate
		
		# 2. PRIORITÉ 2: Taux configuré sur l'article
		item_rate = frappe.get_value("Item", item_code, "gnr_tax_rate")
		if item_rate and is_valid_rate(item_rate):
			log_rate_source(item_code, item_rate, "Configuration article")
			return item_rate
		
		# 3. PRIORITÉ 3: Historique récent de cet article
		historical_rate = get_historical_rate_for_item(item_code, days=30)
		if historical_rate and is_valid_rate(historical_rate):
			log_rate_source(item_code, historical_rate, "Historique récent")
			return historical_rate
		
		# 4. PRIORITÉ 4: Analyse du nom/groupe pour détecter la catégorie
		item_doc = frappe.get_doc("Item", item_code)
		category = detect_gnr_category_from_item(item_code, item_doc.item_name, item_doc.item_group)
		default_rate = get_default_rate_by_category(category)
		
		log_rate_source(item_code, default_rate, f"Catégorie détectée: {category}")
		return default_rate
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux GNR réel pour {item_code}: {str(e)}")
		return get_default_rate_by_category("GNR")


def get_rate_from_source_document(item_code, doc_type, doc_name):
	"""
	Récupère le taux depuis un document source spécifique
	"""
	try:
		if doc_type in ["Sales Invoice", "Purchase Invoice"]:
			return get_rate_from_invoice(item_code, doc_type, doc_name)
		elif doc_type == "Stock Entry":
			return get_rate_from_stock_entry(item_code, doc_name)
		elif doc_type == "Purchase Receipt":
			return get_rate_from_purchase_receipt(item_code, doc_name)
		elif doc_type == "Delivery Note":
			return get_rate_from_delivery_note(item_code, doc_name)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux document source: {str(e)}")
		return None


def get_rate_from_invoice(item_code, doc_type, doc_name):
	"""
	Récupère le taux GNR depuis une facture (achat ou vente)
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
		
		# Analyser les taxes pour cet item
		if hasattr(invoice, 'taxes') and invoice.taxes:
			for tax_row in invoice.taxes:
				if tax_row.description:
					description_lower = tax_row.description.lower()
					gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant', 'diesel']
					
					# Vérifier si c'est une taxe GNR
					if any(keyword in description_lower for keyword in gnr_keywords):
						if target_item.qty > 0 and tax_row.tax_amount:
							# Convertir en litres si nécessaire
							quantity_in_litres = convert_to_litres(target_item.qty, target_item.uom)
							
							if quantity_in_litres > 0:
								taux_calcule = abs(tax_row.tax_amount) / quantity_in_litres
								if is_valid_rate(taux_calcule):
									return taux_calcule
		
		# Si pas de taxe spécifique trouvée, chercher dans les détails de l'item
		if hasattr(target_item, 'gnr_tax_amount') and target_item.gnr_tax_amount:
			quantity_in_litres = convert_to_litres(target_item.qty, target_item.uom)
			if quantity_in_litres > 0:
				taux_calcule = abs(target_item.gnr_tax_amount) / quantity_in_litres
				if is_valid_rate(taux_calcule):
					return taux_calcule
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux facture: {str(e)}")
		return None


def get_rate_from_stock_entry(item_code, doc_name):
	"""
	Récupère le taux depuis une entrée de stock
	"""
	try:
		stock_entry = frappe.get_doc("Stock Entry", doc_name)
		
		# Si lié à une facture, récupérer depuis la facture
		if hasattr(stock_entry, 'purchase_receipt') and stock_entry.purchase_receipt:
			pr = frappe.get_doc("Purchase Receipt", stock_entry.purchase_receipt)
			if hasattr(pr, 'bill_no') and pr.bill_no:
				# Chercher la facture liée
				invoice = frappe.get_all("Purchase Invoice", 
					filters={"bill_no": pr.bill_no, "supplier": pr.supplier},
					limit=1
				)
				if invoice:
					return get_rate_from_invoice(item_code, "Purchase Invoice", invoice[0].name)
		
		# Sinon, utiliser la configuration de l'article
		return frappe.get_value("Item", item_code, "gnr_tax_rate")
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux stock entry: {str(e)}")
		return None


def get_rate_from_purchase_receipt(item_code, doc_name):
	"""
	Récupère le taux depuis un bon de réception
	"""
	try:
		pr = frappe.get_doc("Purchase Receipt", doc_name)
		
		# Chercher une facture liée
		if hasattr(pr, 'bill_no') and pr.bill_no:
			invoice = frappe.get_all("Purchase Invoice",
				filters={"bill_no": pr.bill_no, "supplier": pr.supplier},
				limit=1
			)
			if invoice:
				return get_rate_from_invoice(item_code, "Purchase Invoice", invoice[0].name)
		
		# Chercher par Purchase Order
		for item in pr.items:
			if item.item_code == item_code and item.purchase_order:
				# Chercher une facture liée à cette commande
				invoice = frappe.get_all("Purchase Invoice Item",
					filters={"purchase_order": item.purchase_order, "item_code": item_code},
					fields=["parent"],
					limit=1
				)
				if invoice:
					return get_rate_from_invoice(item_code, "Purchase Invoice", invoice[0].parent)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux bon réception: {str(e)}")
		return None


def get_rate_from_delivery_note(item_code, doc_name):
	"""
	Récupère le taux depuis un bon de livraison
	"""
	try:
		dn = frappe.get_doc("Delivery Note", doc_name)
		
		# Chercher une facture liée
		for item in dn.items:
			if item.item_code == item_code and item.against_sales_invoice:
				return get_rate_from_invoice(item_code, "Sales Invoice", item.against_sales_invoice)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux bon livraison: {str(e)}")
		return None


def get_historical_rate_for_item(item_code, days=30):
	"""
	Récupère le taux historique moyen pour un article
	"""
	try:
		date_limit = getdate(nowdate()) - timedelta(days=days)
		
		# Récupérer les derniers taux utilisés
		result = frappe.db.sql("""
			SELECT taux_gnr, date_mouvement
			FROM `tabMouvement GNR`
			WHERE code_produit = %s 
			AND taux_gnr > 0.1 AND taux_gnr < 50
			AND docstatus = 1
			AND date_mouvement >= %s
			ORDER BY date_mouvement DESC
			LIMIT 10
		""", (item_code, date_limit), as_dict=True)
		
		if not result:
			return None
		
		# Calculer la moyenne pondérée (plus récent = plus de poids)
		total_weight = 0
		weighted_sum = 0
		
		for i, row in enumerate(result):
			weight = len(result) - i  # Plus récent = poids plus élevé
			weighted_sum += row.taux_gnr * weight
			total_weight += weight
		
		if total_weight > 0:
			average_rate = weighted_sum / total_weight
			return flt(average_rate, 3)
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux historique: {str(e)}")
		return None


def detect_gnr_category_from_item(item_code, item_name="", item_group=""):
	"""
	Détecte la catégorie GNR depuis le code/nom/groupe d'article
	"""
	try:
		# Combiner toutes les informations pour l'analyse
		text_to_analyze = f"{item_code} {item_name or ''} {item_group or ''}".upper()
		
		# Règles de détection par ordre de priorité
		if any(keyword in text_to_analyze for keyword in ["ADBLUE", "AD BLUE", "UREA"]):
			return "ADBLUE"
		
		elif any(keyword in text_to_analyze for keyword in ["FIOUL", "FUEL OIL", "HEATING OIL"]):
			if any(bio_keyword in text_to_analyze for bio_keyword in ["BIO", "RENOUVELABLE", "VERT"]):
				return "FIOUL_BIO"
			elif any(winter_keyword in text_to_analyze for winter_keyword in ["HIVER", "WINTER", "ANTIGEL"]):
				return "FIOUL_HIVER"
			else:
				return "FIOUL_STANDARD"
		
		elif any(keyword in text_to_analyze for keyword in ["GAZOLE", "GAZOIL", "DIESEL", "GASOIL"]):
			if any(road_keyword in text_to_analyze for road_keyword in ["ROUTIER", "ROAD", "B7"]):
				return "GAZOLE"
			else:
				return "GNR"  # GNR par défaut pour le gazole
		
		elif any(keyword in text_to_analyze for keyword in ["GNR", "ROUGE", "AGRICOLE", "TRACTEUR"]):
			return "GNR"
		
		elif any(keyword in text_to_analyze for keyword in ["ESSENCE", "GASOLINE", "SP95", "SP98", "E10"]):
			return "ESSENCE"
		
		else:
			# Analyse plus fine du groupe d'articles
			if item_group:
				group_lower = item_group.lower()
				if any(keyword in group_lower for keyword in ["carburant", "combustible", "fuel"]):
					return "GNR"  # Par défaut pour les carburants
			
			return "AUTRE"
		
	except Exception as e:
		frappe.log_error(f"Erreur détection catégorie GNR: {str(e)}")
		return "GNR"


def get_default_rate_by_category(category):
	"""
	Retourne le taux par défaut selon la catégorie
	CES TAUX DOIVENT ÊTRE MIS À JOUR SELON LA RÉGLEMENTATION
	"""
	# Taux au 1er janvier 2025 (à mettre à jour)
	rates = {
		"ADBLUE": 0.0,           # AdBlue non taxé
		"FIOUL_BIO": 3.86,       # Fioul domestique agricole
		"FIOUL_HIVER": 3.86,     # Fioul domestique
		"FIOUL_STANDARD": 3.86,  # Fioul domestique standard
		"GAZOLE": 59.40,         # Gazole routier (TICPE + TVA)
		"GNR": 3.86,             # GNR agricole
		"ESSENCE": 68.29,        # Essence SP95 (TICPE + TVA)
		"AUTRE": 3.86            # Par défaut GNR
	}
	
	return rates.get(category, 3.86)


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
			# Volumes métriques
			'm3': 1000,
			'mètre cube': 1000,
			'cubic meter': 1000,
			'dm3': 1,
			'decimeter cube': 1,
			'cm3': 0.001,
			'millilitre': 0.001,
			'ml': 0.001,
			
			# Unités spécialisées
			'hectolitre': 100,
			'hl': 100,
			'décalitre': 10,
			'dal': 10,
			'centilitre': 0.01,
			'cl': 0.01,
			
			# Unités anglo-saxonnes
			'gallon': 3.78541,
			'gal': 3.78541,
			'quart': 0.946353,
			'pint': 0.473176,
			'fluid ounce': 0.0295735,
			'fl oz': 0.0295735,
			
			# Unités impériales
			'imperial gallon': 4.54609,
			'imp gal': 4.54609,
			'imperial pint': 0.568261,
			'imp pint': 0.568261
		}
		
		# Recherche directe
		if uom_lower in conversion_factors:
			return flt(quantity * conversion_factors[uom_lower], 3)
		
		# Recherche partielle
		for unit, factor in conversion_factors.items():
			if unit in uom_lower:
				return flt(quantity * factor, 3)
		
		# Si aucune conversion trouvée, log et retourner tel quel
		frappe.logger().warning(f"[GNR] UOM non reconnue: {uom}, quantité inchangée")
		return flt(quantity, 3)
		
	except Exception as e:
		frappe.log_error(f"Erreur conversion UOM {uom}: {str(e)}")
		return flt(quantity, 3)


def is_valid_rate(rate):
	"""
	Vérifie si un taux GNR est valide
	"""
	try:
		rate = flt(rate, 3)
		# Fourchette raisonnable pour les taux GNR en France
		return 0.0 <= rate <= 100.0
	except:
		return False


def log_rate_source(item_code, rate, source):
	"""
	Log la source du taux pour traçabilité
	"""
	try:
		if frappe.get_value("GNR Settings", None, "enable_debug_logging"):
			frappe.logger().info(f"[GNR] {item_code}: Taux {rate}€/L depuis {source}")
	except:
		pass


@frappe.whitelist()
def recalculer_tous_les_taux_reels(limite=100, force_recalcul=False):
	"""
	Recalcule tous les mouvements avec des taux suspects ou tous si force_recalcul=True
	"""
	try:
		# Conditions de base
		conditions = ["docstatus = 1"]
		
		if not force_recalcul:
			# Seulement les taux suspects (taux par défaut probables)
			conditions.append("taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81, 59.40, 68.29)")
		
		where_clause = " AND ".join(conditions)
		
		# Récupérer les mouvements à recalculer
		mouvements = frappe.db.sql(f"""
			SELECT name, code_produit, taux_gnr, reference_document, reference_name, quantite
			FROM `tabMouvement GNR`
			WHERE {where_clause}
			ORDER BY creation DESC 
			LIMIT %s
		""", (limite,), as_dict=True)
		
		corriges = 0
		erreurs = 0
		ameliorations = []
		
		for mouvement_data in mouvements:
			try:
				# Recalculer le taux réel
				nouveau_taux = get_real_gnr_rate_for_item(
					mouvement_data.code_produit,
					mouvement_data.reference_document,
					mouvement_data.reference_name
				)
				
				if nouveau_taux and nouveau_taux != mouvement_data.taux_gnr:
					# Mettre à jour le mouvement
					nouveau_montant = flt(mouvement_data.quantite * nouveau_taux, 2)
					
					frappe.db.set_value("Mouvement GNR", mouvement_data.name, {
						"taux_gnr": nouveau_taux,
						"montant_taxe_gnr": nouveau_montant
					})
					
					ameliorations.append({
						"mouvement": mouvement_data.name,
						"code_produit": mouvement_data.code_produit,
						"ancien_taux": mouvement_data.taux_gnr,
						"nouveau_taux": nouveau_taux,
						"difference": flt(nouveau_taux - mouvement_data.taux_gnr, 3)
					})
					
					corriges += 1
				
			except Exception as e:
				frappe.log_error(f"Erreur recalcul mouvement {mouvement_data.name}: {str(e)}")
				erreurs += 1
		
		frappe.db.commit()
		
		return {
			"success": True,
			"total_traites": len(mouvements),
			"corriges": corriges,
			"erreurs": erreurs,
			"ameliorations": ameliorations[:10],  # Limiter pour l'affichage
			"message": f"{corriges} mouvements recalculés avec les vrais taux, {erreurs} erreurs"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur recalcul global taux réels: {str(e)}")
		return {
			"success": False,
			"message": f"Erreur: {str(e)}"
		}


@frappe.whitelist()
def analyser_ecarts_taux():
	"""
	Analyse les écarts entre taux configurés et taux réellement utilisés
	"""
	try:
		# Récupérer les articles avec des mouvements GNR récents
		result = frappe.db.sql("""
			SELECT 
				m.code_produit,
				i.item_name,
				i.gnr_tax_rate as taux_configure,
				AVG(m.taux_gnr) as taux_moyen_utilise,
				COUNT(*) as nb_mouvements,
				MIN(m.taux_gnr) as taux_min,
				MAX(m.taux_gnr) as taux_max,
				STDDEV(m.taux_gnr) as ecart_type
			FROM `tabMouvement GNR` m
			LEFT JOIN `tabItem` i ON m.code_produit = i.name
			WHERE m.docstatus = 1
			AND m.date_mouvement >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
			AND m.taux_gnr > 0.1
			GROUP BY m.code_produit, i.item_name, i.gnr_tax_rate
			HAVING nb_mouvements >= 3
			ORDER BY ABS(taux_configure - taux_moyen_utilise) DESC
		""", as_dict=True)
		
		# Analyser les écarts significatifs
		ecarts_significatifs = []
		recommendations = []
		
		for row in result:
			taux_config = row.taux_configure or 0
			taux_utilise = row.taux_moyen_utilise or 0
			ecart = abs(taux_config - taux_utilise)
			
			if ecart > 0.1:  # Écart > 10 centimes
				ecarts_significatifs.append({
					"code_produit": row.code_produit,
					"item_name": row.item_name,
					"taux_configure": taux_config,
					"taux_moyen_utilise": flt(taux_utilise, 3),
					"ecart": flt(ecart, 3),
					"nb_mouvements": row.nb_mouvements,
					"variabilite": flt(row.ecart_type or 0, 3)
				})
				
				# Recommandation
				if taux_config == 0:
					action = "Configurer"
					nouveau_taux = flt(taux_utilise, 3)
				else:
					action = "Mettre à jour"
					nouveau_taux = flt(taux_utilise, 3)
				
				recommendations.append({
					"code_produit": row.code_produit,
					"action": action,
					"taux_actuel": taux_config,
					"taux_recommande": nouveau_taux,
					"justification": f"Basé sur {row.nb_mouvements} mouvements récents"
				})
		
		return {
			"success": True,
			"total_articles_analyses": len(result),
			"ecarts_significatifs": ecarts_significatifs,
			"recommendations": recommendations,
			"resume": {
				"articles_avec_ecarts": len(ecarts_significatifs),
				"articles_sans_config": len([r for r in result if not r.taux_configure]),
				"articles_bien_configures": len(result) - len(ecarts_significatifs)
			}
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur analyse écarts taux: {str(e)}")
		return {
			"success": False,
			"message": f"Erreur: {str(e)}"
		}


@frappe.whitelist()
def appliquer_taux_recommandes(recommendations):
	"""
	Applique les taux recommandés par l'analyse
	"""
	try:
		if isinstance(recommendations, str):
			recommendations = json.loads(recommendations)
		
		updates = 0
		erreurs = 0
		
		for rec in recommendations:
			try:
				frappe.db.set_value("Item", rec["code_produit"], "gnr_tax_rate", rec["taux_recommande"])
				updates += 1
				
				# Log de la mise à jour
				frappe.logger().info(f"[GNR] Taux mis à jour pour {rec['code_produit']}: {rec['taux_recommande']}€/L")
				
			except Exception as e:
				frappe.log_error(f"Erreur mise à jour {rec['code_produit']}: {str(e)}")
				erreurs += 1
		
		frappe.db.commit()
		
		return {
			"success": True,
			"updates": updates,
			"erreurs": erreurs,
			"message": f"{updates} articles mis à jour, {erreurs} erreurs"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur application taux recommandés: {str(e)}")
		return {
			"success": False,
			"message": f"Erreur: {str(e)}"
		}


def get_gnr_tax_rate_trends(item_code, days=180):
	"""
	Analyse l'évolution des taux GNR pour un article
	"""
	try:
		date_limit = getdate(nowdate()) - timedelta(days=days)
		
		result = frappe.db.sql("""
			SELECT 
				date_mouvement,
				taux_gnr,
				type_mouvement,
				reference_document,
				reference_name
			FROM `tabMouvement GNR`
			WHERE code_produit = %s
			AND taux_gnr > 0.1 AND taux_gnr < 100
			AND docstatus = 1
			AND date_mouvement >= %s
			ORDER BY date_mouvement ASC
		""", (item_code, date_limit), as_dict=True)
		
		if not result:
			return None
		
		# Calculer la tendance
		rates = [row.taux_gnr for row in result]
		dates = [row.date_mouvement for row in result]
		
		# Statistiques de base
		stats = {
			"nb_points": len(rates),
			"taux_min": min(rates),
			"taux_max": max(rates),
			"taux_moyen": sum(rates) / len(rates),
			"volatilite": max(rates) - min(rates),
			"premier_taux": rates[0],
			"dernier_taux": rates[-1],
			"evolution": rates[-1] - rates[0],
			"donnees": result
		}
		
		return stats
		
	except Exception as e:
		frappe.log_error(f"Erreur analyse tendance taux: {str(e)}")
		return None