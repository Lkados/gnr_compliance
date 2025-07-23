# -*- coding: utf-8 -*-
"""
Module de capture des ventes GNR avec prix réels depuis les factures
Chemin: gnr_compliance/integrations/sales.py
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
import re


def capture_vente_gnr(doc, method):
	"""
	Capture automatique des ventes GNR avec vrais taux depuis les factures
	"""
	try:
		if doc.doctype != "Sales Invoice" or doc.docstatus != 1:
			return

		for item in doc.items:
			if is_gnr_product(item.item_code):
				# Récupérer le vrai taux depuis cette facture
				taux_gnr_reel = get_real_gnr_tax_from_invoice(item, doc)
				
				# Créer le mouvement GNR avec le taux réel
				create_gnr_movement_from_sale(doc, item, taux_gnr_reel)
				
	except Exception as e:
		frappe.log_error(f"Erreur capture vente GNR: {str(e)}", "GNR Sales Capture")


def get_real_gnr_tax_from_invoice(item, invoice_doc):
	"""
	Récupère le VRAI taux GNR depuis une facture de vente
	PRIORITÉ: 1.Taxes facture → 2.Item rate → 3.Historique → 4.Défaut
	"""
	try:
		# 1. PRIORITÉ 1: Analyser les taxes réelles de la facture
		if hasattr(invoice_doc, 'taxes') and invoice_doc.taxes:
			for tax_row in invoice_doc.taxes:
				if tax_row.description:
					description_lower = tax_row.description.lower()
					gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant']
					
					if any(keyword in description_lower for keyword in gnr_keywords):
						if item.qty > 0 and tax_row.tax_amount:
							# Calculer le taux par litre
							quantity_in_litres = convert_to_litres(item.qty, item.uom)
							
							if quantity_in_litres > 0:
								taux_calcule = abs(tax_row.tax_amount) / quantity_in_litres
								if 0.1 <= taux_calcule <= 50:  # Vérification cohérence
									frappe.logger().info(f"[GNR] Taux RÉEL trouvé: {taux_calcule}€/L depuis taxe facture")
									return taux_calcule

		# 2. PRIORITÉ 2: Taux configuré sur l'article
		item_doc = frappe.get_doc("Item", item.item_code)
		if hasattr(item_doc, 'gnr_tax_rate') and item_doc.gnr_tax_rate:
			if 0.1 <= item_doc.gnr_tax_rate <= 50:
				return item_doc.gnr_tax_rate

		# 3. PRIORITÉ 3: Historique de cet article spécifique
		historical_rate = get_historical_rate_for_item(item.item_code)
		if historical_rate:
			return historical_rate

		# 4. DERNIER RECOURS: Analyse du nom pour détecter la catégorie
		category = detect_gnr_category_from_item(item.item_code, item.item_name)
		default_rate = get_default_rate_by_category(category)
		
		frappe.logger().warning(f"[GNR] Taux par défaut utilisé pour {item.item_code}: {default_rate}€/L")
		return default_rate

	except Exception as e:
		frappe.log_error(f"Erreur récupération taux réel: {str(e)}")
		return get_default_rate_by_category("GNR")


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


def is_gnr_product(item_code):
	"""
	Détermine si un article est soumis à la taxe GNR
	"""
	if not item_code:
		return False
	
	try:
		item_doc = frappe.get_doc("Item", item_code)
		
		# Vérifier les groupes d'articles pour détecter les carburants
		if item_doc.item_group:
			group_lower = item_doc.item_group.lower()
			fuel_groups = ['carburant', 'combustible', 'gazole', 'fioul', 'gnr', 'essence']
			
			if any(group in group_lower for group in fuel_groups):
				return True
		
		# Vérifier le nom de l'article
		item_name_lower = (item_doc.item_name or item_code).lower()
		fuel_keywords = ['gazole', 'fioul', 'gnr', 'diesel', 'fuel', 'carburant', 'combustible']
		
		return any(keyword in item_name_lower for keyword in fuel_keywords)
		
	except Exception:
		return False


def create_gnr_movement_from_sale(invoice_doc, item, taux_gnr):
	"""
	Crée un mouvement GNR depuis une vente avec le taux réel
	"""
	try:
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
			"client_fournisseur": invoice_doc.customer,
			"statut": "Validé",
			"notes": f"Mouvement automatique depuis facture {invoice_doc.name}"
		})
		
		mouvement_gnr.insert()
		mouvement_gnr.submit()
		
		frappe.logger().info(f"[GNR] Mouvement créé: {mouvement_gnr.name} - Taux: {taux_gnr}€/L")
		
	except Exception as e:
		frappe.log_error(f"Erreur création mouvement GNR vente: {str(e)}")


def get_historical_rate_for_item(item_code):
	"""
	Récupère le dernier taux utilisé pour un article spécifique
	"""
	try:
		result = frappe.db.sql("""
			SELECT taux_gnr 
			FROM `tabMouvement GNR` 
			WHERE code_produit = %s 
			AND taux_gnr > 0.1 AND taux_gnr < 50
			AND docstatus = 1 
			ORDER BY date_mouvement DESC 
			LIMIT 1
		""", (item_code,))
		
		return result[0][0] if result else None
		
	except Exception:
		return None


def detect_gnr_category_from_item(item_code, item_name=""):
	"""
	Détecte la catégorie GNR depuis le code/nom d'article
	"""
	text = f"{item_code} {item_name or ''}".upper()
	
	if "ADBLUE" in text or "AD BLUE" in text:
		return "ADBLUE"
	elif "FIOUL" in text or "FUEL" in text:
		if "BIO" in text:
			return "FIOUL_BIO"
		elif "HIVER" in text:
			return "FIOUL_HIVER"
		else:
			return "FIOUL_STANDARD"
	elif "GAZOLE" in text or "GAZOIL" in text:
		return "GAZOLE"
	else:
		return "GNR"


def get_default_rate_by_category(category):
	"""
	TAUX PAR DÉFAUT - utilisés seulement en dernier recours
	Ces taux doivent être mis à jour selon la réglementation
	"""
	rates = {
		"ADBLUE": 0.0,       # AdBlue non taxé
		"FIOUL_BIO": 3.86,   # Fioul agricole
		"FIOUL_HIVER": 3.86, 
		"FIOUL_STANDARD": 3.86,
		"GAZOLE": 24.81,     # Gazole routier
		"GNR": 24.81         # GNR standard
	}
	return rates.get(category, 24.81)


@frappe.whitelist()
def recalculer_ventes_gnr(date_debut=None, date_fin=None):
	"""
	Recalcule les mouvements GNR pour les ventes avec les vrais taux
	"""
	try:
		if not date_debut:
			date_debut = nowdate()
		if not date_fin:
			date_fin = nowdate()
		
		# Chercher les factures de vente dans la période
		invoices = frappe.get_all("Sales Invoice", 
			filters={
				"docstatus": 1,
				"posting_date": ["between", [date_debut, date_fin]]
			},
			fields=["name", "posting_date", "customer"]
		)
		
		recalculated = 0
		for invoice_data in invoices:
			invoice = frappe.get_doc("Sales Invoice", invoice_data.name)
			
			for item in invoice.items:
				if is_gnr_product(item.item_code):
					# Supprimer l'ancien mouvement s'il existe
					existing_movements = frappe.get_all("Mouvement GNR",
						filters={
							"reference_document": "Sales Invoice",
							"reference_name": invoice.name,
							"code_produit": item.item_code
						}
					)
					
					for movement in existing_movements:
						frappe.delete_doc("Mouvement GNR", movement.name)
					
					# Recréer avec le vrai taux
					taux_reel = get_real_gnr_tax_from_invoice(item, invoice)
					create_gnr_movement_from_sale(invoice, item, taux_reel)
					recalculated += 1
		
		return {
			"success": True,
			"message": f"{recalculated} mouvements GNR recalculés avec les vrais taux"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur recalcul ventes GNR: {str(e)}")
		return {
			"success": False,
			"message": f"Erreur: {str(e)}"
		}


def update_item_gnr_rate_from_usage(item_code, new_rate):
	"""
	Met à jour le taux GNR d'un article basé sur l'usage réel
	"""
	try:
		if 0.1 <= new_rate <= 50:  # Validation du taux
			frappe.db.set_value("Item", item_code, "gnr_tax_rate", new_rate)
			frappe.db.commit()
			
			frappe.logger().info(f"[GNR] Taux mis à jour pour {item_code}: {new_rate}€/L")
			return True
		else:
			frappe.logger().warning(f"[GNR] Taux invalide pour {item_code}: {new_rate}€/L")
			return False
			
	except Exception as e:
		frappe.log_error(f"Erreur mise à jour taux GNR: {str(e)}")
		return False


def get_average_rate_for_item(item_code, days=30):
	"""
	Calcule le taux moyen pour un article sur une période
	"""
	try:
		from datetime import timedelta
		
		date_limite = getdate(nowdate()) - timedelta(days=days)
		
		result = frappe.db.sql("""
			SELECT AVG(taux_gnr) as avg_rate, COUNT(*) as count
			FROM `tabMouvement GNR`
			WHERE code_produit = %s 
			AND taux_gnr > 0.1 AND taux_gnr < 50
			AND date_mouvement >= %s
			AND docstatus = 1
		""", (item_code, date_limite), as_dict=True)
		
		if result and result[0].avg_rate:
			return {
				"average_rate": flt(result[0].avg_rate, 3),
				"sample_size": result[0].count
			}
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur calcul taux moyen: {str(e)}")
		return None