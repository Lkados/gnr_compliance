import frappe
from frappe.utils import flt

# Groupe d'articles GNR officiel
GNR_ITEM_GROUP = "Combustibles/Carburants/GNR"

@frappe.whitelist()
def nettoyer_configuration_gnr():
	"""
	Nettoie complètement la configuration GNR pour ne garder que les articles du bon groupe
	"""
	try:
		print("\n🧹 NETTOYAGE COMPLET DE LA CONFIGURATION GNR")
		print("=" * 60)
		
		# 1. Réinitialiser TOUS les articles
		print(f"\n1️⃣ Réinitialisation de tous les articles...")
		
		result = frappe.db.sql("""
			UPDATE `tabItem`
			SET is_gnr_tracked = 0,
			    gnr_tracked_category = NULL,
			    gnr_tax_rate = 0
			WHERE is_gnr_tracked = 1
		""")
		
		nb_reset = frappe.db.sql("SELECT COUNT(*) FROM `tabItem` WHERE is_gnr_tracked = 1")[0][0]
		print(f"   ✅ {nb_reset} articles réinitialisés")
		
		# 2. Identifier les articles du groupe GNR
		print(f"\n2️⃣ Identification des articles dans le groupe '{GNR_ITEM_GROUP}'...")
		
		articles_gnr = frappe.db.sql("""
			SELECT name, item_code, item_name
			FROM `tabItem`
			WHERE item_group = %s
		""", (GNR_ITEM_GROUP,), as_dict=True)
		
		print(f"   📊 {len(articles_gnr)} articles trouvés dans le groupe GNR")
		
		if len(articles_gnr) == 0:
			print(f"   ⚠️ ATTENTION: Aucun article dans le groupe '{GNR_ITEM_GROUP}'")
			print(f"   Vérifiez que ce groupe existe et contient des articles")
			return {
				"success": False,
				"message": f"Aucun article trouvé dans le groupe {GNR_ITEM_GROUP}"
			}
		
		# 3. Marquer uniquement ces articles comme GNR
		print(f"\n3️⃣ Configuration des articles GNR...")
		
		articles_configures = 0
		for article in articles_gnr:
			try:
				frappe.db.set_value("Item", article.name, {
					"is_gnr_tracked": 1,
					"gnr_tracked_category": "GNR",
					"gnr_tax_rate": 0  # Pas de taux par défaut - doit venir des factures
				})
				articles_configures += 1
				
				if articles_configures <= 10:  # Afficher les 10 premiers
					print(f"   ✓ {article.item_code}: {article.item_name or 'Sans nom'}")
				elif articles_configures == 11:
					print(f"   ... et {len(articles_gnr) - 10} autres articles")
					
			except Exception as e:
				print(f"   ❌ Erreur sur {article.item_code}: {str(e)}")
		
		# 4. Vérifier les autres groupes suspects
		print(f"\n4️⃣ Vérification d'autres groupes similaires...")
		
		autres_groupes = frappe.db.sql("""
			SELECT DISTINCT item_group, COUNT(*) as nb_articles
			FROM `tabItem`
			WHERE (item_group LIKE '%Combustible%'
			   OR item_group LIKE '%Carburant%'
			   OR item_group LIKE '%Fioul%'
			   OR item_group LIKE '%Gazole%'
			   OR item_group LIKE '%GNR%')
			AND item_group != %s
			GROUP BY item_group
			ORDER BY nb_articles DESC
		""", (GNR_ITEM_GROUP,), as_dict=True)
		
		if autres_groupes:
			print(f"   📋 Autres groupes similaires trouvés:")
			for groupe in autres_groupes:
				print(f"      - {groupe.item_group}: {groupe.nb_articles} articles")
		else:
			print(f"   ✅ Aucun autre groupe similaire trouvé")
		
		# 5. Commit des changements
		frappe.db.commit()
		
		print(f"\n✅ NETTOYAGE TERMINÉ")
		print(f"📊 Résumé:")
		print(f"   - Articles dans le groupe GNR: {len(articles_gnr)}")
		print(f"   - Articles configurés: {articles_configures}")
		print(f"   - Taux par défaut: AUCUN (récupération depuis factures)")
		
		return {
			"success": True,
			"articles_configures": articles_configures,
			"groupe_utilise": GNR_ITEM_GROUP,
			"message": f"{articles_configures} articles GNR configurés (groupe uniquement)"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur nettoyage GNR: {str(e)}")
		print(f"❌ ERREUR: {str(e)}")
		return {"success": False, "error": str(e)}

@frappe.whitelist()
def verifier_configuration_post_nettoyage():
	"""
	Vérifie la configuration après nettoyage
	"""
	try:
		print("\n🔍 VÉRIFICATION POST-NETTOYAGE")
		print("=" * 40)
		
		# Articles correctement configurés
		articles_ok = frappe.db.sql("""
			SELECT COUNT(*) as count
			FROM `tabItem`
			WHERE is_gnr_tracked = 1
			AND item_group = %s
		""", (GNR_ITEM_GROUP,), as_dict=True)[0].count
		
		# Articles mal configurés (marqués GNR mais pas dans le bon groupe)
		articles_mal_configures = frappe.db.sql("""
			SELECT name, item_code, item_name, item_group
			FROM `tabItem`
			WHERE is_gnr_tracked = 1
			AND item_group != %s
		""", (GNR_ITEM_GROUP,), as_dict=True)
		
		# Articles dans le groupe mais pas marqués
		articles_non_marques = frappe.db.sql("""
			SELECT name, item_code, item_name
			FROM `tabItem`
			WHERE item_group = %s
			AND (is_gnr_tracked = 0 OR is_gnr_tracked IS NULL)
		""", (GNR_ITEM_GROUP,), as_dict=True)
		
		# Articles avec taux par défaut (à éviter)
		articles_avec_taux_defaut = frappe.db.sql("""
			SELECT name, item_code, gnr_tax_rate
			FROM `tabItem`
			WHERE is_gnr_tracked = 1
			AND gnr_tax_rate > 0
		""", as_dict=True)
		
		print(f"✅ Articles correctement configurés: {articles_ok}")
		print(f"❌ Articles mal configurés: {len(articles_mal_configures)}")
		print(f"⚠️ Articles non marqués dans le groupe: {len(articles_non_marques)}")
		print(f"⚠️ Articles avec taux par défaut: {len(articles_avec_taux_defaut)}")
		
		if articles_mal_configures:
			print(f"\n❌ Articles mal configurés:")
			for art in articles_mal_configures[:5]:
				print(f"   - {art.item_code} (groupe: {art.item_group})")
		
		if articles_non_marques:
			print(f"\n⚠️ Articles du groupe GNR non marqués:")
			for art in articles_non_marques[:5]:
				print(f"   - {art.item_code}: {art.item_name}")
		
		if articles_avec_taux_defaut:
			print(f"\n⚠️ Articles avec taux par défaut (devrait être 0):")
			for art in articles_avec_taux_defaut[:5]:
				print(f"   - {art.item_code}: {art.gnr_tax_rate}€/L")
		
		qualite = "EXCELLENT" if len(articles_mal_configures) == 0 and len(articles_non_marques) == 0 else "À CORRIGER"
		
		return {
			"success": True,
			"qualite": qualite,
			"articles_ok": articles_ok,
			"articles_mal_configures": len(articles_mal_configures),
			"articles_non_marques": len(articles_non_marques),
			"articles_avec_taux_defaut": len(articles_avec_taux_defaut),
			"details": {
				"mal_configures": articles_mal_configures,
				"non_marques": articles_non_marques,
				"avec_taux_defaut": articles_avec_taux_defaut
			}
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur vérification post-nettoyage: {str(e)}")
		return {"success": False, "error": str(e)}

@frappe.whitelist()
def analyser_factures_sans_taux_gnr(limite=20):
	"""
	Analyse les factures récentes avec articles GNR mais sans taux détecté
	"""
	try:
		print("\n🔍 ANALYSE DES FACTURES SANS TAUX GNR")
		print("=" * 45)
		
		# Factures de vente récentes avec articles GNR
		factures_vente = frappe.db.sql("""
			SELECT DISTINCT
				si.name,
				si.posting_date,
				si.customer,
				COUNT(sii.name) as nb_items_gnr
			FROM `tabSales Invoice` si
			JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
			JOIN `tabItem` i ON sii.item_code = i.name
			WHERE si.docstatus = 1
			AND i.item_group = %s
			AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			GROUP BY si.name
			ORDER BY si.posting_date DESC
			LIMIT %s
		""", (GNR_ITEM_GROUP, limite), as_dict=True)
		
		print(f"📊 {len(factures_vente)} factures de vente récentes avec articles GNR")
		
		factures_analysees = []
		for facture in factures_vente:
			# Vérifier si des mouvements GNR existent
			mouvements = frappe.db.count("Mouvement GNR", {
				"reference_document": "Sales Invoice",
				"reference_name": facture.name,
				"docstatus": 1
			})
			
			# Analyser les taxes de cette facture
			taxes_gnr = analyser_taxes_facture("Sales Invoice", facture.name)
			
			factures_analysees.append({
				"nom": facture.name,
				"date": facture.posting_date,
				"client": facture.customer,
				"nb_items_gnr": facture.nb_items_gnr,
				"mouvements_crees": mouvements,
				"taxes_gnr_detectees": len(taxes_gnr),
				"taxes_details": taxes_gnr
			})
		
		# Statistiques
		sans_mouvements = [f for f in factures_analysees if f["mouvements_crees"] == 0]
		avec_taxes_gnr = [f for f in factures_analysees if f["taxes_gnr_detectees"] > 0]
		
		print(f"❌ Factures sans mouvements GNR: {len(sans_mouvements)}")
		print(f"✅ Factures avec taxes GNR détectées: {len(avec_taxes_gnr)}")
		
		if sans_mouvements:
			print(f"\n📋 Exemples de factures sans mouvements:")
			for f in sans_mouvements[:3]:
				print(f"   - {f['nom']} ({f['date']}) - {f['client']} - {f['nb_items_gnr']} articles GNR")
				if f['taxes_details']:
					print(f"     Taxes: {', '.join([t['description'] for t in f['taxes_details']])}")
		
		return {
			"success": True,
			"total_factures": len(factures_vente),
			"sans_mouvements": len(sans_mouvements),
			"avec_taxes_gnr": len(avec_taxes_gnr),
			"factures_details": factures_analysees
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur analyse factures: {str(e)}")
		return {"success": False, "error": str(e)}

def analyser_taxes_facture(doctype, docname):
	"""
	Analyse les taxes d'une facture pour détecter les taxes GNR
	"""
	try:
		doc = frappe.get_doc(doctype, docname)
		
		taxes_gnr = []
		if hasattr(doc, 'taxes') and doc.taxes:
			for tax in doc.taxes:
				if tax.description:
					desc_lower = tax.description.lower()
					gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant']
					
					if any(keyword in desc_lower for keyword in gnr_keywords):
						taxes_gnr.append({
							"description": tax.description,
							"rate": tax.rate,
							"tax_amount": tax.tax_amount,
							"account_head": tax.account_head
						})
		
		return taxes_gnr
		
	except Exception as e:
		frappe.log_error(f"Erreur analyse taxes facture {docname}: {str(e)}")
		return []

@frappe.whitelist()
def creer_champs_personnalises_gnr():
	"""
	Crée les champs personnalisés nécessaires pour le taux GNR dans les factures
	"""
	try:
		print("\n⚙️ CRÉATION DES CHAMPS PERSONNALISÉS GNR")
		print("=" * 45)
		
		# Champ dans Sales Invoice Item
		if not frappe.db.exists("Custom Field", "Sales Invoice Item-custom_taux_gnr"):
			custom_field = frappe.get_doc({
				"doctype": "Custom Field",
				"dt": "Sales Invoice Item",
				"fieldname": "custom_taux_gnr",
				"label": "Taux GNR (€/L)",
				"fieldtype": "Currency",
				"insert_after": "rate",
				"description": "Taux GNR appliqué à cet article en €/L"
			})
			custom_field.insert()
			print("✅ Champ 'custom_taux_gnr' créé pour Sales Invoice Item")
		else:
			print("✅ Champ 'custom_taux_gnr' existe déjà pour Sales Invoice Item")
		
		# Champ dans Purchase Invoice Item
		if not frappe.db.exists("Custom Field", "Purchase Invoice Item-custom_taux_gnr"):
			custom_field = frappe.get_doc({
				"doctype": "Custom Field",
				"dt": "Purchase Invoice Item",
				"fieldname": "custom_taux_gnr",
				"label": "Taux GNR (€/L)",
				"fieldtype": "Currency",
				"insert_after": "rate",
				"description": "Taux GNR appliqué à cet article en €/L"
			})
			custom_field.insert()
			print("✅ Champ 'custom_taux_gnr' créé pour Purchase Invoice Item")
		else:
			print("✅ Champ 'custom_taux_gnr' existe déjà pour Purchase Invoice Item")
		
		return {
			"success": True,
			"message": "Champs personnalisés GNR créés avec succès"
		}
		
	except Exception as e:
		frappe.log_error(f"Erreur création champs personnalisés: {str(e)}")
		return {"success": False, "error": str(e)}

