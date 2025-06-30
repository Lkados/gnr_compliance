# -*- coding: utf-8 -*-
"""
Module de gestion des mouvements de stock GNR avec prix réels
Chemin: gnr_compliance/integrations/stock.py
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from gnr_compliance.integrations.sales import (
	is_gnr_product, 
	convert_to_litres, 
	detect_gnr_category_from_item, 
	get_default_rate_by_category,
	get_historical_rate_for_item
)


def capture_stock_gnr(doc, method):
	"""
	Capture automatique des mouvements de stock GNR
	"""
	try:
		if doc.doctype != "Stock Entry" or doc.docstatus != 1:
			return

		for item in doc.items:
			if is_gnr_product(item.item_code):
				create_gnr_movement_from_stock(doc, item)
				
	except Exception as e:
		frappe.log_error(f"Erreur capture stock GNR: {str(e)}", "GNR Stock Capture")


def create_gnr_movement_from_stock(stock_doc, item):
	"""
	Crée un mouvement GNR depuis un mouvement de stock avec taux réel
	"""
	try:
		# Récupérer le taux réel pour cet article
		taux_gnr_reel = get_real_tax_rate_for_stock_item(item.item_code, stock_doc)
		
		# Déterminer le type de mouvement et la quantité
		movement_type, quantity = determine_stock_movement_type(stock_doc, item)
		
		if quantity == 0:
			return  # Pas de mouvement significatif
		
		quantity_litres = convert_to_litres(abs(quantity), item.uom)
		montant_taxe = flt(quantity_litres * taux_gnr_reel, 2)
		
		# Déterminer le client/fournisseur selon le type
		client_fournisseur = get_client_fournisseur_from_stock(stock_doc, movement_type)
		
		mouvement_gnr = frappe.get_doc({
			"doctype": "Mouvement GNR",
			"type_mouvement": movement_type,
			"date_mouvement": getdate(stock_doc.posting_date),
			"reference_document": "Stock Entry",
			"reference_name": stock_doc.name,
			"code_produit": item.item_code,
			"nom_produit": item.item_name,
			"quantite": quantity_litres,
			"unite": "Litre",
			"taux_gnr": taux_gnr_reel,
			"montant_taxe_gnr": montant_taxe,
			"client_fournisseur": client_fournisseur,
			"entrepot_source": item.s_warehouse,
			"entrepot_destination": item.t_warehouse,
			"statut": "Validé",
			"notes": f"Mouvement automatique depuis entrée stock {stock_doc.name} - {stock_doc.stock_entry_type}"
		})
		
		mouvement_gnr.insert()
		mouvement_gnr.submit()
		
		frappe.logger().info(f"[GNR] Mouvement stock créé: {mouvement_gnr.name} - Taux: {taux_gnr_reel}€/L")
		
	except Exception as e:
		frappe.log_error(f"Erreur création mouvement GNR stock: {str(e)}")


def get_real_tax_rate_for_stock_item(item_code, stock_doc=None):
	"""
	Récupère le taux réel pour un article dans les mouvements de stock
	PRIORITÉ: 1.Facture d'achat liée → 2.Taux article → 3.Historique → 4.Défaut
	"""
	try:
		# 1. PRIORITÉ 1: Si c'est une réception liée à une facture d'achat
		if stock_doc and hasattr(stock_doc, 'purchase_receipt_details'):
			purchase_rate = get_rate_from_linked_purchase(item_code, stock_doc)
			if purchase_rate:
				return purchase_rate
		
		# 2. PRIORITÉ 2: Taux configuré sur l'article
		item_rate = frappe.get_value("Item", item_code, "gnr_tax_rate")
		if item_rate and 0.1 <= item_rate <= 50:
			return item_rate
		
		# 3. PRIORITÉ 3: Historique des mouvements
		historical_rate = get_historical_rate_for_item(item_code)
		if historical_rate:
			return historical_rate
		
		# 4. PRIORITÉ 4: Analyse du nom de l'article
		item_name = frappe.get_value("Item", item_code, "item_name")
		category = detect_gnr_category_from_item(item_code, item_name)
		default_rate = get_default_rate_by_category(category)
		
		frappe.logger().warning(f"[GNR] Taux par défaut utilisé pour stock {item_code}: {default_rate}€/L")
		return default_rate
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux stock: {str(e)}")
		return get_default_rate_by_category("GNR")


def get_rate_from_linked_purchase(item_code, stock_doc):
	"""
	Récupère le taux depuis une facture d'achat liée
	"""
	try:
		# Chercher les factures d'achat liées à cette entrée de stock
		if stock_doc.purchase_receipt:
			# Via bon de réception
			purchase_receipts = frappe.get_all("Purchase Receipt Item",
				filters={
					"parent": stock_doc.purchase_receipt,
					"item_code": item_code
				},
				fields=["purchase_invoice", "rate", "qty"]
			)
			
			for pr_item in purchase_receipts:
				if pr_item.purchase_invoice:
					return get_gnr_rate_from_purchase_invoice(item_code, pr_item.purchase_invoice)
		
		# Recherche directe par référence
		if hasattr(stock_doc, 'purchase_order') and stock_doc.purchase_order:
			# Via commande d'achat
			purchase_invoices = frappe.get_all("Purchase Invoice Item",
				filters={
					"purchase_order": stock_doc.purchase_order,
					"item_code": item_code
				},
				fields=["parent"]
			)
			
			for pi_item in purchase_invoices:
				rate = get_gnr_rate_from_purchase_invoice(item_code, pi_item.parent)
				if rate:
					return rate
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux achat lié: {str(e)}")
		return None


def get_gnr_rate_from_purchase_invoice(item_code, invoice_name):
	"""
	Récupère le taux GNR depuis une facture d'achat spécifique
	"""
	try:
		invoice = frappe.get_doc("Purchase Invoice", invoice_name)
		
		# Chercher l'item dans la facture
		for item in invoice.items:
			if item.item_code == item_code:
				# Analyser les taxes pour cet item
				if hasattr(invoice, 'taxes') and invoice.taxes:
					for tax_row in invoice.taxes:
						if tax_row.description:
							description_lower = tax_row.description.lower()
							gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant']
							
							if any(keyword in description_lower for keyword in gnr_keywords):
								if item.qty > 0 and tax_row.tax_amount:
									quantity_in_litres = convert_to_litres(item.qty, item.uom)
									
									if quantity_in_litres > 0:
										taux_calcule = abs(tax_row.tax_amount) / quantity_in_litres
										if 0.1 <= taux_calcule <= 50:
											frappe.logger().info(f"[GNR] Taux RÉEL trouvé depuis facture achat: {taux_calcule}€/L")
											return taux_calcule
		
		return None
		
	except Exception as e:
		frappe.log_error(f"Erreur récupération taux facture achat: {str(e)}")
		return None


def determine_stock_movement_type(stock_doc, item):
	"""
	Détermine le type de mouvement et la quantité significative
	"""
	movement_type = "Transfert"  # Par défaut
	quantity = 0
	
	try:
		# Analyser le type d'entrée de stock
		if stock_doc.stock_entry_type == "Material Receipt":
			movement_type = "Entrée"
			quantity = item.qty
			
		elif stock_doc.stock_entry_type == "Material Issue":
			movement_type = "Sortie"
			quantity = -item.qty
			
		elif stock_doc.stock_entry_type == "Material Transfer":
			movement_type = "Transfert"
			quantity = item.qty
			
		elif stock_doc.stock_entry_type == "Manufacture":
			if item.s_warehouse:  # Consommation de matière première
				movement_type = "Consommation"
				quantity = -item.qty
			elif item.t_warehouse:  # Production de produit fini
				movement_type = "Production"
				quantity = item.qty
				
		elif stock_doc.stock_entry_type == "Repack":
			movement_type = "Reconditionnement"
			quantity = item.qty if item.t_warehouse else -item.qty
			
		else:
			# Autres types
			if item.t_warehouse and not item.s_warehouse:
				movement_type = "Entrée"
				quantity = item.qty
			elif item.s_warehouse and not item.t_warehouse:
				movement_type = "Sortie"
				quantity = -item.qty
			else:
				movement_type = "Transfert"
				quantity = item.qty
		
		return movement_type, quantity
		
	except Exception as e:
		frappe.log_error(f"Erreur détermination type mouvement: {str(e)}")
		return "Transfert", item.qty


def get_client_fournisseur_from_stock(stock_doc, movement_type):
	"""
	Détermine le client/fournisseur depuis le mouvement de stock
	"""
	try:
		# Fournisseur pour les entrées
		if movement_type in ["Entrée", "Réception"] and stock_doc.supplier:
			return stock_doc.supplier
		
		# Client pour les sorties
		if movement_type in ["Sortie", "Livraison"] and stock_doc.customer:
			return stock_doc.customer
		
		# Recherche dans les documents liés
		if stock_doc.purchase_receipt:
			pr = frappe.get_value("Purchase Receipt", stock_doc.purchase_receipt, "supplier")
			if pr:
				return pr
		
		if stock_doc.delivery_note:
			dn = frappe.get_value("Delivery Note", stock_doc.delivery_note, "customer")
			if dn:
				return dn
		
		# Recherche par commande
		if hasattr(stock_doc, 'purchase_order') and stock_doc.purchase_order:
			po_supplier = frappe.get_value("Purchase Order", stock_doc.purchase_order, "supplier")
			if po_supplier:
				return po_supplier
		
		if hasattr(stock_doc, 'sales_order') and stock_doc.sales_order:
			so_customer = frappe.get_value("Sales Order", stock_doc.sales_order, "customer")
			if so_customer:
				return so_customer
		
		return None
		
	except Exception:
		return None


@frappe.whitelist()
def recalculer_stocks_gnr(date_debut=None, date_fin=None):
	"""
	Recalcule les mouvements GNR pour les stocks avec les vrais taux
	"""
	try:
		if not date_debut:
			date_debut = nowdate()
		if not date_fin:
			date_fin = nowdate()
		
		# Chercher les entrées de stock dans la période
		stock_entries = frappe.get_all("Stock Entry", 
			filters={
				"docstatus": 1,
				"posting_date": ["between", [date_debut, date_fin]]
			},
			fields=["name", "posting_date", "stock_entry_type", "supplier", "customer"]
		)
		
		recalculated = 0
		for entry_data in stock_entries:
			stock_entry = frappe.get_doc("Stock Entry", entry_data.name)
			
			for item in stock_entry.items:
				if is_gnr_product(item.item_code):
					# Supprimer l'ancien mouvement s'il existe
					existing_movements = frappe.get_all("Mouvement GNR",
						filters={
							"reference_document": "Stock Entry",
							"reference_name": stock_entry.name,
							"code_produit": item.item_code
						}
					)
					
					for movement in existing_movements:
						frappe.delete_doc("Mouvement GNR", movement.name)
					
					# Recréer avec le vrai taux
					create_gnr_movement_from_stock(stock_entry, item)
					recalculated += 1
		
		return {
			"success": True,
			"message": f"{recalculated} mouvements GNR stock recalculés avec les vrais taux"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur recalcul stocks GNR: {str(e)}")
		return {
			"success": False,
			"message": f"Erreur: {str(e)}"
		}


def validate_gnr_stock_movement(doc, method):
	"""
	Valide les mouvements de stock pour les produits GNR
	"""
	try:
		if doc.doctype != "Stock Entry":
			return
		
		for item in doc.items:
			if is_gnr_product(item.item_code):
				# Vérifier que le taux GNR est configuré
				taux = get_real_tax_rate_for_stock_item(item.item_code, doc)
				
				if taux == 0:
					frappe.msgprint(
						_("Attention: Aucun taux GNR configuré pour l'article {0}").format(item.item_code),
						alert=True
					)
				
				# Log pour traçabilité
				frappe.logger().info(f"[GNR] Validation stock {item.item_code} - Taux: {taux}€/L")
		
	except Exception as e:
		frappe.log_error(f"Erreur validation mouvement stock GNR: {str(e)}")


def get_stock_gnr_summary(warehouse=None, date_from=None, date_to=None):
	"""
	Résumé des mouvements GNR par entrepôt
	"""
	try:
		conditions = ["m.docstatus = 1"]
		values = []
		
		if warehouse:
			conditions.append("(m.entrepot_source = %s OR m.entrepot_destination = %s)")
			values.extend([warehouse, warehouse])
		
		if date_from:
			conditions.append("m.date_mouvement >= %s")
			values.append(date_from)
		
		if date_to:
			conditions.append("m.date_mouvement <= %s")
			values.append(date_to)
		
		where_clause = " AND ".join(conditions)
		
		result = frappe.db.sql(f"""
			SELECT 
				m.code_produit,
				m.nom_produit,
				SUM(CASE WHEN m.type_mouvement = 'Entrée' THEN m.quantite ELSE 0 END) as entrees,
				SUM(CASE WHEN m.type_mouvement = 'Sortie' THEN m.quantite ELSE 0 END) as sorties,
				SUM(CASE WHEN m.type_mouvement = 'Transfert' THEN m.quantite ELSE 0 END) as transferts,
				AVG(m.taux_gnr) as taux_moyen,
				SUM(m.montant_taxe_gnr) as montant_total_taxe
			FROM `tabMouvement GNR` m
			WHERE {where_clause}
			AND m.reference_document = 'Stock Entry'
			GROUP BY m.code_produit, m.nom_produit
			ORDER BY montant_total_taxe DESC
		""", values, as_dict=True)
		
		return result
		
	except Exception as e:
		frappe.log_error(f"Erreur résumé stock GNR: {str(e)}")
		return []


@frappe.whitelist()
def update_stock_gnr_rates():
	"""
	Met à jour automatiquement les taux GNR basés sur les dernières factures
	"""
	try:
		updated_items = []
		
		# Récupérer tous les articles GNR
		gnr_items = frappe.db.sql("""
			SELECT DISTINCT code_produit
			FROM `tabMouvement GNR`
			WHERE docstatus = 1
		""", as_dict=True)
		
		for item_data in gnr_items:
			item_code = item_data.code_produit
			
			# Calculer le taux moyen des 10 derniers mouvements
			recent_rates = frappe.db.sql("""
				SELECT taux_gnr
				FROM `tabMouvement GNR`
				WHERE code_produit = %s
				AND taux_gnr > 0.1 AND taux_gnr < 50
				AND docstatus = 1
				ORDER BY date_mouvement DESC
				LIMIT 10
			""", (item_code,))
			
			if recent_rates:
				rates = [rate[0] for rate in recent_rates]
				average_rate = sum(rates) / len(rates)
				
				# Mettre à jour l'article si le taux a changé significativement
				current_rate = frappe.get_value("Item", item_code, "gnr_tax_rate") or 0
				
				if abs(average_rate - current_rate) > 0.1:  # Différence > 0.1€
					frappe.db.set_value("Item", item_code, "gnr_tax_rate", flt(average_rate, 3))
					updated_items.append({
						"item_code": item_code,
						"old_rate": current_rate,
						"new_rate": flt(average_rate, 3)
					})
		
		frappe.db.commit()
		
		return {
			"success": True,
			"updated_items": updated_items,
			"message": f"{len(updated_items)} articles mis à jour avec les nouveaux taux"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur mise à jour taux stock: {str(e)}")
		return {
			"success": False,
			"message": f"Erreur: {str(e)}"
		}