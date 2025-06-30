# -*- coding: utf-8 -*-
"""
DocType Mouvement GNR avec calcul automatique des taux réels
Chemin: gnr_compliance/gnr_compliance/doctype/mouvement_gnr/mouvement_gnr.py
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate
from gnr_compliance.integrations.sales import (
	detect_gnr_category_from_item,
	get_default_rate_by_category,
	get_historical_rate_for_item
)


class MouvementGNR(Document):
	def before_insert(self):
		"""Actions avant insertion"""
		self.calculer_taux_et_montants()
		self.valider_donnees()
	
	def before_save(self):
		"""Actions avant sauvegarde"""
		self.calculer_taux_et_montants()
		self.valider_donnees()
	
	def on_submit(self):
		"""Actions lors de la soumission"""
		self.mettre_a_jour_statistiques()
		self.creer_ecriture_comptable()
	
	def on_cancel(self):
		"""Actions lors de l'annulation"""
		self.annuler_ecriture_comptable()


	def calculer_taux_et_montants(self):
		"""
		Calcule automatiquement les taux et montants avec VRAIS TAUX depuis les sources
		"""
		try:
			# 1. Si pas de taux, récupérer depuis les sources réelles
			if not self.taux_gnr or self.taux_gnr == 0:
				self.taux_gnr = self.get_real_taux_gnr_from_all_sources()
			
			# 2. Calculer le montant de la taxe
			if self.quantite and self.taux_gnr:
				self.montant_taxe_gnr = flt(self.quantite * self.taux_gnr, 2)
			
			# 3. Calculer le montant HT si pas renseigné
			if not self.montant_ht and self.quantite:
				# Estimation basée sur un prix moyen si disponible
				prix_moyen = self.get_prix_moyen_article()
				if prix_moyen:
					self.montant_ht = flt(self.quantite * prix_moyen, 2)
			
			# 4. Mettre à jour les dates
			if not self.date_mouvement:
				self.date_mouvement = nowdate()
				
		except Exception as e:
			frappe.log_error(f"Erreur calcul taux GNR réels: {str(e)}")


	def get_real_taux_gnr_from_all_sources(self):
		"""
		Récupère le taux réel depuis toutes les sources possibles
		PRIORITÉ: 1.Document référence → 2.Article → 3.Historique → 4.Défaut
		"""
		if not self.code_produit:
			return 0
		
		try:
			# 1. PRIORITÉ 1: Depuis le document de référence (facture)
			if self.reference_document and self.reference_name:
				doc_rate = self.get_taux_from_reference_document()
				if doc_rate and 0.1 <= doc_rate <= 50:
					return doc_rate
			
			# 2. PRIORITÉ 2: Taux de l'article
			item_rate = frappe.get_value("Item", self.code_produit, "gnr_tax_rate") 
			if item_rate and item_rate > 0:
				return item_rate
			
			# 3. PRIORITÉ 3: Historique de cet article
			historical = get_historical_rate_for_item(self.code_produit)
			if historical:
				return historical
			
			# 4. PRIORITÉ 4: Analyse du nom pour déterminer la catégorie
			item_name = frappe.get_value("Item", self.code_produit, "item_name")
			category = detect_gnr_category_from_item(self.code_produit, item_name)
			default_rate = get_default_rate_by_category(category)
			
			frappe.logger().warning(f"[GNR] Taux par défaut utilisé pour {self.code_produit}: {default_rate}€/L")
			return default_rate
			
		except Exception as e:
			frappe.log_error(f"Erreur récupération taux toutes sources: {str(e)}")
			return get_default_rate_by_category("GNR")


	def get_taux_from_reference_document(self):
		"""
		Récupère le taux depuis le document de référence
		"""
		try:
			if not self.reference_document or not self.reference_name:
				return None
			
			# Facture de vente
			if self.reference_document == "Sales Invoice":
				return self.get_taux_from_sales_invoice()
			
			# Facture d'achat
			elif self.reference_document == "Purchase Invoice":
				return self.get_taux_from_purchase_invoice()
			
			# Entrée de stock
			elif self.reference_document == "Stock Entry":
				return self.get_taux_from_stock_entry()
			
			return None
			
		except Exception as e:
			frappe.log_error(f"Erreur récupération taux document référence: {str(e)}")
			return None


	def get_taux_from_sales_invoice(self):
		"""Récupère le taux depuis une facture de vente"""
		try:
			invoice = frappe.get_doc("Sales Invoice", self.reference_name)
			
			# Chercher l'item correspondant
			for item in invoice.items:
				if item.item_code == self.code_produit:
					# Analyser les taxes
					if hasattr(invoice, 'taxes') and invoice.taxes:
						for tax_row in invoice.taxes:
							if tax_row.description:
								description_lower = tax_row.description.lower()
								gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant']
								
								if any(keyword in description_lower for keyword in gnr_keywords):
									if item.qty > 0 and tax_row.tax_amount:
										from gnr_compliance.integrations.sales import convert_to_litres
										quantity_in_litres = convert_to_litres(item.qty, item.uom)
										
										if quantity_in_litres > 0:
											taux_calcule = abs(tax_row.tax_amount) / quantity_in_litres
											if 0.1 <= taux_calcule <= 50:
												return taux_calcule
			return None
			
		except Exception as e:
			frappe.log_error(f"Erreur récupération taux facture vente: {str(e)}")
			return None


	def get_taux_from_purchase_invoice(self):
		"""Récupère le taux depuis une facture d'achat"""
		try:
			invoice = frappe.get_doc("Purchase Invoice", self.reference_name)
			
			# Chercher l'item correspondant
			for item in invoice.items:
				if item.item_code == self.code_produit:
					# Analyser les taxes
					if hasattr(invoice, 'taxes') and invoice.taxes:
						for tax_row in invoice.taxes:
							if tax_row.description:
								description_lower = tax_row.description.lower()
								gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant']
								
								if any(keyword in description_lower for keyword in gnr_keywords):
									if item.qty > 0 and tax_row.tax_amount:
										from gnr_compliance.integrations.sales import convert_to_litres
										quantity_in_litres = convert_to_litres(item.qty, item.uom)
										
										if quantity_in_litres > 0:
											taux_calcule = abs(tax_row.tax_amount) / quantity_in_litres
											if 0.1 <= taux_calcule <= 50:
												return taux_calcule
			return None
			
		except Exception as e:
			frappe.log_error(f"Erreur récupération taux facture achat: {str(e)}")
			return None


	def get_taux_from_stock_entry(self):
		"""Récupère le taux depuis une entrée de stock"""
		try:
			# Pour les entrées de stock, utiliser l'historique ou la configuration de l'article
			item_rate = frappe.get_value("Item", self.code_produit, "gnr_tax_rate")
			if item_rate and item_rate > 0:
				return item_rate
			
			# Sinon, historique
			return get_historical_rate_for_item(self.code_produit)
			
		except Exception as e:
			frappe.log_error(f"Erreur récupération taux entrée stock: {str(e)}")
			return None


	def get_prix_moyen_article(self):
		"""Récupère le prix moyen de l'article"""
		try:
			# Prix depuis les dernières transactions
			result = frappe.db.sql("""
				SELECT AVG(montant_ht / quantite) as prix_moyen
				FROM `tabMouvement GNR`
				WHERE code_produit = %s 
				AND montant_ht > 0 AND quantite > 0
				AND docstatus = 1
				AND date_mouvement >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
			""", (self.code_produit,))
			
			if result and result[0][0]:
				return flt(result[0][0], 2)
			
			# Prix standard de l'article
			return frappe.get_value("Item", self.code_produit, "standard_rate") or 0
			
		except Exception:
			return 0


	def valider_donnees(self):
		"""Validation des données du mouvement"""
		try:
			# Validation du code produit
			if not self.code_produit:
				frappe.throw(_("Code produit requis"))
			
			# Validation de la quantité
			if not self.quantite or self.quantite <= 0:
				frappe.throw(_("Quantité doit être positive"))
			
			# Validation du taux GNR
			if not self.taux_gnr or self.taux_gnr < 0:
				frappe.throw(_("Taux GNR doit être positif"))
			
			if self.taux_gnr > 50:
				frappe.msgprint(_("Attention: Taux GNR très élevé ({0}€/L)").format(self.taux_gnr), alert=True)
			
			# Validation des dates
			if self.date_mouvement and getdate(self.date_mouvement) > getdate(nowdate()):
				frappe.throw(_("Date de mouvement ne peut pas être dans le futur"))
			
			# Validation du type de mouvement
			if not self.type_mouvement:
				self.type_mouvement = "Autre"
			
		except Exception as e:
			frappe.log_error(f"Erreur validation mouvement GNR: {str(e)}")
			raise


	def mettre_a_jour_statistiques(self):
		"""Met à jour les statistiques d'utilisation"""
		try:
			# Incrémenter le compteur d'utilisation de l'article
			current_count = frappe.get_value("Item", self.code_produit, "total_gnr_movements") or 0
			frappe.db.set_value("Item", self.code_produit, "total_gnr_movements", current_count + 1)
			
			# Mettre à jour la dernière date d'utilisation
			frappe.db.set_value("Item", self.code_produit, "last_gnr_movement_date", self.date_mouvement)
			
			# Log pour traçabilité
			frappe.logger().info(f"[GNR] Statistiques mises à jour pour {self.code_produit}")
			
		except Exception as e:
			frappe.log_error(f"Erreur mise à jour statistiques: {str(e)}")


	def creer_ecriture_comptable(self):
		"""Crée l'écriture comptable pour la taxe GNR"""
		try:
			# Configuration des comptes
			compte_taxe_gnr = frappe.get_value("Company", self.company, "compte_taxe_gnr")
			compte_contrepartie = frappe.get_value("Company", self.company, "compte_carburant")
			
			if not compte_taxe_gnr or not compte_contrepartie:
				frappe.logger().warning(f"[GNR] Comptes comptables non configurés pour {self.company}")
				return
			
			# Créer l'écriture journal
			journal_entry = frappe.get_doc({
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"posting_date": self.date_mouvement,
				"company": self.company,
				"remark": f"Taxe GNR - {self.type_mouvement} - {self.code_produit} - {self.name}",
				"user_remark": f"Mouvement GNR automatique depuis {self.name}",
				"accounts": [
					{
						"account": compte_taxe_gnr,
						"debit_in_account_currency": self.montant_taxe_gnr,
						"credit_in_account_currency": 0,
						"reference_type": "Mouvement GNR",
						"reference_name": self.name
					},
					{
						"account": compte_contrepartie,
						"debit_in_account_currency": 0,
						"credit_in_account_currency": self.montant_taxe_gnr,
						"reference_type": "Mouvement GNR",
						"reference_name": self.name
					}
				]
			})
			
			journal_entry.insert()
			journal_entry.submit()
			
			# Lier l'écriture au mouvement
			self.db_set("journal_entry", journal_entry.name)
			
			frappe.logger().info(f"[GNR] Écriture comptable créée: {journal_entry.name}")
			
		except Exception as e:
			frappe.log_error(f"Erreur création écriture comptable: {str(e)}")


	def annuler_ecriture_comptable(self):
		"""Annule l'écriture comptable associée"""
		try:
			if self.journal_entry:
				journal_entry = frappe.get_doc("Journal Entry", self.journal_entry)
				if journal_entry.docstatus == 1:
					journal_entry.cancel()
					frappe.logger().info(f"[GNR] Écriture comptable annulée: {self.journal_entry}")
				
		except Exception as e:
			frappe.log_error(f"Erreur annulation écriture comptable: {str(e)}")


	def get_mouvement_summary(self):
		"""Retourne un résumé du mouvement pour l'affichage"""
		return {
			"code_produit": self.code_produit,
			"nom_produit": self.nom_produit,
			"quantite": self.quantite,
			"unite": self.unite,
			"taux_gnr": self.taux_gnr,
			"montant_taxe_gnr": self.montant_taxe_gnr,
			"type_mouvement": self.type_mouvement,
			"date_mouvement": self.date_mouvement,
			"client_fournisseur": self.client_fournisseur,
			"reference": f"{self.reference_document} - {self.reference_name}" if self.reference_document else None
		}


# MÉTHODES GLOBALES

@frappe.whitelist()
def recalculer_mouvement_gnr(mouvement_name):
	"""
	Recalcule un mouvement GNR spécifique avec les vrais taux
	"""
	try:
		mouvement = frappe.get_doc("Mouvement GNR", mouvement_name)
		
		# Sauvegarder l'ancien taux pour comparaison
		ancien_taux = mouvement.taux_gnr
		
		# Forcer le recalcul du taux
		mouvement.taux_gnr = 0
		mouvement.calculer_taux_et_montants()
		
		# Sauvegarder
		mouvement.save()
		
		return {
			"success": True,
			"ancien_taux": ancien_taux,
			"nouveau_taux": mouvement.taux_gnr,
			"difference": flt(mouvement.taux_gnr - ancien_taux, 3),
			"nouveau_montant": mouvement.montant_taxe_gnr
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur recalcul mouvement GNR: {str(e)}")
		return {
			"success": False,
			"message": str(e)
		}


@frappe.whitelist()
def recalculer_tous_les_taux_reels(limite=100):
	"""
	Recalcule tous les mouvements avec des taux suspects
	"""
	try:
		# Chercher les mouvements avec taux par défaut suspects
		mouvements = frappe.db.sql("""
			SELECT name, code_produit, taux_gnr, reference_document, reference_name
			FROM `tabMouvement GNR`
			WHERE docstatus = 1 
			AND taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81)
			ORDER BY creation DESC 
			LIMIT %s
		""", (limite,), as_dict=True)
		
		corriges = 0
		erreurs = 0
		
		for mouvement_data in mouvements:
			try:
				result = recalculer_mouvement_gnr(mouvement_data.name)
				if result["success"]:
					corriges += 1
				else:
					erreurs += 1
			except Exception:
				erreurs += 1
		
		frappe.db.commit()
		
		return {
			"success": True,
			"total_traites": len(mouvements),
			"corriges": corriges,
			"erreurs": erreurs,
			"message": f"{corriges} mouvements recalculés avec succès, {erreurs} erreurs"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur recalcul global: {str(e)}")
		return {
			"success": False,
			"message": str(e)
		}


@frappe.whitelist()
def get_gnr_statistics(date_from=None, date_to=None):
	"""
	Statistiques des mouvements GNR
	"""
	try:
		conditions = ["docstatus = 1"]
		values = []
		
		if date_from:
			conditions.append("date_mouvement >= %s")
			values.append(date_from)
		
		if date_to:
			conditions.append("date_mouvement <= %s")
			values.append(date_to)
		
		where_clause = " AND ".join(conditions)
		
		# Statistiques globales
		global_stats = frappe.db.sql(f"""
			SELECT 
				COUNT(*) as total_mouvements,
				SUM(quantite) as total_quantite,
				SUM(montant_taxe_gnr) as total_taxe,
				AVG(taux_gnr) as taux_moyen,
				MIN(taux_gnr) as taux_min,
				MAX(taux_gnr) as taux_max
			FROM `tabMouvement GNR`
			WHERE {where_clause}
		""", values, as_dict=True)
		
		# Répartition par type
		by_type = frappe.db.sql(f"""
			SELECT 
				type_mouvement,
				COUNT(*) as nb_mouvements,
				SUM(quantite) as quantite_totale,
				SUM(montant_taxe_gnr) as taxe_totale
			FROM `tabMouvement GNR`
			WHERE {where_clause}
			GROUP BY type_mouvement
			ORDER BY taxe_totale DESC
		""", values, as_dict=True)
		
		# Top produits
		top_products = frappe.db.sql(f"""
			SELECT 
				code_produit,
				nom_produit,
				COUNT(*) as nb_mouvements,
				SUM(quantite) as quantite_totale,
				SUM(montant_taxe_gnr) as taxe_totale,
				AVG(taux_gnr) as taux_moyen
			FROM `tabMouvement GNR`
			WHERE {where_clause}
			GROUP BY code_produit, nom_produit
			ORDER BY taxe_totale DESC
			LIMIT 10
		""", values, as_dict=True)
		
		return {
			"success": True,
			"global_stats": global_stats[0] if global_stats else {},
			"by_type": by_type,
			"top_products": top_products
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur statistiques GNR: {str(e)}")
		return {
			"success": False,
			"message": str(e)
		}


def validate_gnr_movement(doc, method):
	"""Hook de validation pour les mouvements GNR"""
	if doc.doctype == "Mouvement GNR":
		doc.valider_donnees()


def update_gnr_rates_from_movements():
	"""Met à jour les taux GNR des articles basés sur les mouvements récents"""
	try:
		# Récupérer tous les articles avec mouvements GNR
		items_with_movements = frappe.db.sql("""
			SELECT DISTINCT code_produit
			FROM `tabMouvement GNR`
			WHERE docstatus = 1
			AND date_mouvement >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
		""", as_dict=True)
		
		updated_count = 0
		
		for item_data in items_with_movements:
			item_code = item_data.code_produit
			
			# Calculer le taux moyen des 5 derniers mouvements
			recent_rates = frappe.db.sql("""
				SELECT taux_gnr
				FROM `tabMouvement GNR`
				WHERE code_produit = %s
				AND taux_gnr > 0.1 AND taux_gnr < 50
				AND docstatus = 1
				ORDER BY date_mouvement DESC
				LIMIT 5
			""", (item_code,))
			
			if recent_rates and len(recent_rates) >= 3:  # Au moins 3 mouvements
				rates = [rate[0] for rate in recent_rates]
				average_rate = sum(rates) / len(rates)
				
				# Mettre à jour si différence significative
				current_rate = frappe.get_value("Item", item_code, "gnr_tax_rate") or 0
				
				if abs(average_rate - current_rate) > 0.05:  # Différence > 5 centimes
					frappe.db.set_value("Item", item_code, "gnr_tax_rate", flt(average_rate, 3))
					updated_count += 1
		
		frappe.db.commit()
		frappe.logger().info(f"[GNR] {updated_count} articles mis à jour avec les nouveaux taux")
		
	except Exception as e:
		frappe.log_error(f"Erreur mise à jour taux depuis mouvements: {str(e)}")