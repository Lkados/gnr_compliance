# gnr_compliance/utils/gnr_validation.py
# Utilitaires pour valider et corriger les taux GNR

import frappe
from frappe import _
from frappe.utils import getdate, flt, now_datetime
import json

@frappe.whitelist()
def analyser_taux_gnr_existants():
    """
    Analyse les taux GNR actuels dans les mouvements pour détecter les incohérences
    """
    try:
        # Récupérer tous les mouvements avec leurs taux
        mouvements = frappe.db.sql("""
            SELECT 
                m.name,
                m.code_produit,
                m.date_mouvement,
                m.quantite,
                m.taux_gnr,
                m.montant_taxe_gnr,
                m.prix_unitaire,
                m.reference_document,
                m.reference_name,
                i.item_name,
                -- Calculer si le montant taxe correspond au taux
                CASE 
                    WHEN m.taux_gnr > 0 AND m.quantite > 0
                    THEN ABS((m.quantite * m.taux_gnr) - COALESCE(m.montant_taxe_gnr, 0))
                    ELSE 0
                END as ecart_calcul,
                -- Vérifier si le taux semble réaliste
                CASE 
                    WHEN m.taux_gnr = 0 THEN 'ZERO'
                    WHEN m.taux_gnr < 0.50 THEN 'TROP_BAS'
                    WHEN m.taux_gnr > 50 THEN 'TROP_HAUT'
                    WHEN m.taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 'SUSPECT_DEFAUT'
                    ELSE 'OK'
                END as statut_taux
            FROM `tabMouvement GNR` m
            LEFT JOIN `tabItem` i ON m.code_produit = i.name
            WHERE m.docstatus = 1
            ORDER BY m.date_mouvement DESC
        """, as_dict=True)
        
        # Analyser les résultats
        statistiques = {
            'total_mouvements': len(mouvements),
            'avec_taux_zero': 0,
            'taux_trop_bas': 0,
            'taux_trop_haut': 0,
            'taux_suspects': 0,
            'ecarts_calcul': 0,
            'mouvements_problematiques': [],
            'par_produit': {},
            'par_periode': {}
        }
        
        for mouvement in mouvements:
            statut = mouvement.get('statut_taux')
            ecart = mouvement.get('ecart_calcul', 0)
            
            # Statistiques globales
            if statut == 'ZERO':
                statistiques['avec_taux_zero'] += 1
            elif statut == 'TROP_BAS':
                statistiques['taux_trop_bas'] += 1
            elif statut == 'TROP_HAUT':
                statistiques['taux_trop_haut'] += 1
            elif statut == 'SUSPECT_DEFAUT':
                statistiques['taux_suspects'] += 1
            
            if ecart > 0.01:  # Ecart > 1 centime
                statistiques['ecarts_calcul'] += 1
            
            # Statistiques par produit
            produit = mouvement.get('code_produit')
            if produit not in statistiques['par_produit']:
                statistiques['par_produit'][produit] = {
                    'item_name': mouvement.get('item_name'),
                    'total': 0,
                    'problemes': 0,
                    'taux_min': 999,
                    'taux_max': 0,
                    'taux_moyen': 0,
                    'total_taux': 0
                }
            
            stats_produit = statistiques['par_produit'][produit]
            stats_produit['total'] += 1
            stats_produit['total_taux'] += mouvement.get('taux_gnr', 0)
            stats_produit['taux_min'] = min(stats_produit['taux_min'], mouvement.get('taux_gnr', 0))
            stats_produit['taux_max'] = max(stats_produit['taux_max'], mouvement.get('taux_gnr', 0))
            
            if statut != 'OK' or ecart > 0.01:
                stats_produit['problemes'] += 1
            
            # Statistiques par période (trimestre)
            if mouvement.get('date_mouvement'):
                date_obj = getdate(mouvement['date_mouvement'])
                trimestre_key = f"{date_obj.year}-T{((date_obj.month - 1) // 3) + 1}"
                
                if trimestre_key not in statistiques['par_periode']:
                    statistiques['par_periode'][trimestre_key] = {
                        'total': 0,
                        'problemes': 0,
                        'taux_moyen': 0,
                        'total_taux': 0
                    }
                
                stats_periode = statistiques['par_periode'][trimestre_key]
                stats_periode['total'] += 1
                stats_periode['total_taux'] += mouvement.get('taux_gnr', 0)
                
                if statut != 'OK' or ecart > 0.01:
                    stats_periode['problemes'] += 1
            
            # Collecter les mouvements problématiques
            if statut != 'OK' or ecart > 0.01:
                statistiques['mouvements_problematiques'].append({
                    'name': mouvement.name,
                    'code_produit': mouvement.code_produit,
                    'item_name': mouvement.item_name,
                    'date_mouvement': mouvement.date_mouvement,
                    'taux_gnr': mouvement.taux_gnr,
                    'montant_taxe_gnr': mouvement.montant_taxe_gnr,
                    'statut': statut,
                    'ecart_calcul': ecart,
                    'reference_document': mouvement.reference_document,
                    'reference_name': mouvement.reference_name
                })
        
        # Calculer les moyennes
        for produit_stats in statistiques['par_produit'].values():
            if produit_stats['total'] > 0:
                produit_stats['taux_moyen'] = produit_stats['total_taux'] / produit_stats['total']
                produit_stats['pourcentage_problemes'] = (produit_stats['problemes'] / produit_stats['total']) * 100
        
        for periode_stats in statistiques['par_periode'].values():
            if periode_stats['total'] > 0:
                periode_stats['taux_moyen'] = periode_stats['total_taux'] / periode_stats['total']
                periode_stats['pourcentage_problemes'] = (periode_stats['problemes'] / periode_stats['total']) * 100
        
        return {
            'success': True,
            'statistiques': statistiques,
            'recommandations': generer_recommandations(statistiques)
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur analyse taux GNR: {str(e)}")
        return {'success': False, 'error': str(e)}

def generer_recommandations(stats):
    """Génère des recommandations basées sur l'analyse"""
    recommandations = []
    
    total = stats['total_mouvements']
    if total == 0:
        return [{'type': 'info', 'message': 'Aucun mouvement GNR à analyser'}]
    
    if stats['avec_taux_zero'] > 0:
        pourcentage = (stats['avec_taux_zero'] / total) * 100
        recommandations.append({
            'type': 'warning',
            'message': f"{stats['avec_taux_zero']} mouvements ({pourcentage:.1f}%) avec taux GNR = 0€. Vérifiez si c'est normal (ex: AdBlue, produits non taxés).",
            'action': 'review_zero_rates'
        })
    
    if stats['taux_suspects'] > 0:
        pourcentage = (stats['taux_suspects'] / total) * 100
        recommandations.append({
            'type': 'error',
            'message': f"{stats['taux_suspects']} mouvements ({pourcentage:.1f}%) utilisent des taux par défaut suspects (1.77, 3.86, 6.83, 2.84, 24.81€). Récupérez les vrais taux depuis les factures.",
            'action': 'fix_default_rates'
        })
    
    if stats['ecarts_calcul'] > 0:
        pourcentage = (stats['ecarts_calcul'] / total) * 100
        recommandations.append({
            'type': 'warning',
            'message': f"{stats['ecarts_calcul']} mouvements ({pourcentage:.1f}%) ont des écarts entre le montant taxe enregistré et le calcul (quantité × taux). Recalculez les montants.",
            'action': 'recalculate_amounts'
        })
    
    if stats['taux_trop_bas'] > 0 or stats['taux_trop_haut'] > 0:
        total_aberrants = stats['taux_trop_bas'] + stats['taux_trop_haut']
        pourcentage = (total_aberrants / total) * 100
        recommandations.append({
            'type': 'error',
            'message': f"{total_aberrants} mouvements ({pourcentage:.1f}%) ont des taux aberrants (< 0.50€ ou > 50€). Vérifiez les données sources.",
            'action': 'review_aberrant_rates'
        })
    
    # Recommandations par produit
    produits_problematiques = [
        p for p in stats['par_produit'].values() 
        if p.get('pourcentage_problemes', 0) > 20
    ]
    
    if produits_problematiques:
        recommandations.append({
            'type': 'info',
            'message': f"{len(produits_problematiques)} produit(s) ont plus de 20% de mouvements problématiques. Vérifiez la configuration des taux par produit.",
            'action': 'review_product_rates'
        })
    
    if not recommandations:
        recommandations.append({
            'type': 'success',
            'message': '✅ Toutes les données semblent cohérentes ! Les taux GNR utilisés paraissent réels.',
            'action': None
        })
    
    return recommandations

@frappe.whitelist()
def corriger_taux_depuis_factures(movement_name=None, all_movements=False, limite=100):
    """
    Corrige les taux GNR en récupérant les vrais montants depuis les factures
    
    Args:
        movement_name: Nom d'un mouvement spécifique à corriger
        all_movements: Corriger tous les mouvements suspects
        limite: Nombre maximum de mouvements à traiter (sécurité)
    """
    try:
        if movement_name:
            # Corriger un mouvement spécifique
            mouvements = [frappe.get_doc("Mouvement GNR", movement_name)]
        elif all_movements:
            # Corriger tous les mouvements suspects
            mouvements_suspects = frappe.get_all("Mouvement GNR",
                filters={
                    "docstatus": 1,
                    "taux_gnr": ["in", [1.77, 3.86, 6.83, 2.84, 24.81]]  # Taux suspects par défaut
                },
                limit=limite  # Traiter par lots pour éviter les timeouts
            )
            mouvements = [frappe.get_doc("Mouvement GNR", m.name) for m in mouvements_suspects]
        else:
            return {'success': False, 'message': 'Paramètres manquants'}
        
        corriges = 0
        echecs = 0
        details_corrections = []
        
        for mouvement_doc in mouvements:
            try:
                ancien_taux = mouvement_doc.taux_gnr
                result = corriger_mouvement_depuis_facture(mouvement_doc)
                
                if result['success']:
                    corriges += 1
                    details_corrections.append({
                        'mouvement': mouvement_doc.name,
                        'produit': mouvement_doc.code_produit,
                        'ancien_taux': ancien_taux,
                        'nouveau_taux': result['nouveau_taux'],
                        'source': result['source']
                    })
                else:
                    echecs += 1
                    details_corrections.append({
                        'mouvement': mouvement_doc.name,
                        'produit': mouvement_doc.code_produit,
                        'erreur': result['message']
                    })
            except Exception as e:
                frappe.log_error(f"Erreur correction mouvement {mouvement_doc.name}: {str(e)}")
                echecs += 1
        
        return {
            'success': True,
            'corriges': corriges,
            'echecs': echecs,
            'message': f"{corriges} mouvements corrigés avec vrais taux, {echecs} échecs",
            'details': details_corrections
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur correction taux depuis factures: {str(e)}")
        return {'success': False, 'error': str(e)}

def corriger_mouvement_depuis_facture(mouvement_doc):
    """
    Corrige un mouvement GNR en récupérant les données de la facture source
    
    Returns:
        dict: Résultat de la correction avec détails
    """
    try:
        if not mouvement_doc.reference_document or not mouvement_doc.reference_name:
            return {'success': False, 'message': 'Aucune facture de référence'}
        
        # Récupérer la facture source
        if mouvement_doc.reference_document in ["Sales Invoice", "Purchase Invoice"]:
            try:
                facture = frappe.get_doc(mouvement_doc.reference_document, mouvement_doc.reference_name)
            except frappe.DoesNotExistError:
                return {'success': False, 'message': 'Facture de référence introuvable'}
            
            # Trouver l'article correspondant dans la facture
            for item in facture.items:
                if item.item_code == mouvement_doc.code_produit:
                    # Récupérer le vrai taux depuis la facture
                    result = extraire_taux_gnr_depuis_facture(facture, item)
                    
                    if result['success'] and result['taux'] != mouvement_doc.taux_gnr:
                        nouveau_taux = result['taux']
                        nouveau_montant = mouvement_doc.quantite * nouveau_taux
                        
                        # Mettre à jour le mouvement (cancel + amend pour traçabilité)
                        try:
                            # Annuler l'ancien mouvement
                            mouvement_doc.cancel()
                            
                            # Créer un nouveau mouvement avec les bons taux
                            nouveau_mouvement = frappe.copy_doc(mouvement_doc)
                            nouveau_mouvement.taux_gnr = nouveau_taux
                            nouveau_mouvement.montant_taxe_gnr = nouveau_montant
                            nouveau_mouvement.prix_unitaire = item.rate  # Mettre à jour aussi le prix
                            nouveau_mouvement.insert(ignore_permissions=True)
                            nouveau_mouvement.submit()
                            
                            frappe.logger().info(f"Mouvement {mouvement_doc.name} corrigé: taux {mouvement_doc.taux_gnr} → {nouveau_taux} (source: {result['source']})")
                            
                            return {
                                'success': True,
                                'nouveau_taux': nouveau_taux,
                                'source': result['source'],
                                'nouveau_mouvement': nouveau_mouvement.name
                            }
                        except Exception as e:
                            frappe.log_error(f"Erreur mise à jour mouvement {mouvement_doc.name}: {str(e)}")
                            return {'success': False, 'message': f'Erreur mise à jour: {str(e)}'}
                    else:
                        return {'success': False, 'message': result.get('message', 'Taux identique ou non trouvé')}
            
            return {'success': False, 'message': 'Article non trouvé dans la facture'}
        
        return {'success': False, 'message': 'Type de document non supporté'}
        
    except Exception as e:
        frappe.log_error(f"Erreur correction mouvement {mouvement_doc.name}: {str(e)}")
        return {'success': False, 'message': str(e)}

def extraire_taux_gnr_depuis_facture(facture, item):
    """
    Extrait le vrai taux GNR depuis une facture
    
    Returns:
        dict: Résultat avec taux trouvé et source
    """
    try:
        # 1. Chercher dans les taxes de la facture
        if hasattr(facture, 'taxes') and facture.taxes:
            for tax_row in facture.taxes:
                if tax_row.description:
                    description_lower = tax_row.description.lower()
                    gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant']
                    if any(keyword in description_lower for keyword in gnr_keywords):
                        if item.qty > 0 and tax_row.tax_amount:
                            taux_calcule = abs(tax_row.tax_amount) / item.qty
                            if 0.1 <= taux_calcule <= 50:  # Vérification de cohérence
                                return {
                                    'success': True,
                                    'taux': taux_calcule,
                                    'source': f'Taxe facture: {tax_row.description}'
                                }
        
        # 2. Chercher dans un champ personnalisé de l'item de la facture
        if hasattr(item, 'gnr_tax_rate') and item.gnr_tax_rate:
            if 0.1 <= item.gnr_tax_rate <= 50:
                return {
                    'success': True,
                    'taux': item.gnr_tax_rate,
                    'source': 'Champ item facture'
                }
        
        # 3. Utiliser le taux défini sur l'article maître comme fallback
        taux_article = frappe.get_value("Item", item.item_code, "gnr_tax_rate")
        if taux_article and 0.1 <= taux_article <= 50:
            return {
                'success': True,
                'taux': taux_article,
                'source': 'Article maître'
            }
        
        # 4. Essayer de déduire depuis d'autres éléments de la facture
        # Analyser les commentaires ou descriptions pour des indices de taux
        if hasattr(facture, 'terms') and facture.terms:
            # Rechercher des patterns comme "3.86€/L", "taxe 2.84", etc.
            import re
            pattern = r'(\d+[.,]\d+)\s*[€]\s*[/]?\s*[Ll]?'
            matches = re.findall(pattern, facture.terms)
            if matches:
                for match in matches:
                    taux_potentiel = float(match.replace(',', '.'))
                    if 0.1 <= taux_potentiel <= 50:
                        return {
                            'success': True,
                            'taux': taux_potentiel,
                            'source': 'Termes de la facture'
                        }
        
        return {
            'success': False,
            'message': 'Aucun taux GNR trouvé dans la facture'
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur extraction taux facture: {str(e)}")
        return {'success': False, 'message': str(e)}

@frappe.whitelist()
def rapport_taux_gnr_periode(from_date, to_date):
    """Génère un rapport détaillé des taux GNR réels sur une période"""
    try:
        # Analyse globale des taux
        rapport = frappe.db.sql("""
            SELECT 
                m.code_produit,
                i.item_name,
                COUNT(*) as nb_mouvements,
                AVG(m.taux_gnr) as taux_moyen,
                MIN(m.taux_gnr) as taux_min,
                MAX(m.taux_gnr) as taux_max,
                STDDEV(m.taux_gnr) as ecart_type,
                SUM(m.quantite) as quantite_totale,
                SUM(m.montant_taxe_gnr) as taxe_totale,
                -- Calculer le taux moyen pondéré par les quantités (PLUS PRÉCIS)
                SUM(m.montant_taxe_gnr) / SUM(m.quantite) as taux_pondere_reel,
                -- Analyser la dispersion des taux
                COUNT(DISTINCT m.taux_gnr) as nb_taux_differents,
                -- Détecter les taux suspects
                COUNT(CASE WHEN m.taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as nb_taux_suspects,
                COUNT(CASE WHEN m.taux_gnr = 0 THEN 1 END) as nb_taux_zero,
                -- Analyser par type de client
                SUM(CASE 
                    WHEN c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL 
                    THEN m.quantite 
                    ELSE 0 
                END) as volume_avec_attestation,
                SUM(CASE 
                    WHEN c.custom_n_dossier_ IS NULL OR c.custom_n_dossier_ = '' OR c.custom_date_de_depot IS NULL
                    THEN m.quantite 
                    ELSE 0 
                END) as volume_sans_attestation
            FROM `tabMouvement GNR` m
            LEFT JOIN `tabItem` i ON m.code_produit = i.name
            LEFT JOIN `tabCustomer` c ON m.client = c.name
            WHERE m.date_mouvement BETWEEN %s AND %s
            AND m.docstatus = 1
            AND m.type_mouvement = 'Vente'
            AND m.quantite > 0
            GROUP BY m.code_produit, i.item_name
            ORDER BY quantite_totale DESC
        """, (from_date, to_date), as_dict=True)
        
        # Analyse temporelle (évolution des taux)
        evolution = frappe.db.sql("""
            SELECT 
                YEAR(m.date_mouvement) as annee,
                QUARTER(m.date_mouvement) as trimestre,
                COUNT(*) as nb_mouvements,
                AVG(m.taux_gnr) as taux_moyen,
                SUM(m.montant_taxe_gnr) / SUM(m.quantite) as taux_pondere,
                COUNT(CASE WHEN m.taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as nb_suspects
            FROM `tabMouvement GNR` m
            WHERE m.date_mouvement BETWEEN %s AND %s
            AND m.docstatus = 1
            AND m.type_mouvement = 'Vente'
            AND m.quantite > 0
            GROUP BY YEAR(m.date_mouvement), QUARTER(m.date_mouvement)
            ORDER BY annee, trimestre
        """, (from_date, to_date), as_dict=True)
        
        # Top 10 des clients par volume pour analyse des taux
        top_clients = frappe.db.sql("""
            SELECT 
                m.client,
                c.customer_name,
                SUM(m.quantite) as volume_total,
                AVG(m.taux_gnr) as taux_moyen_client,
                SUM(m.montant_taxe_gnr) / SUM(m.quantite) as taux_pondere_client,
                CASE 
                    WHEN c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL 
                    THEN 'Avec attestation' 
                    ELSE 'Sans attestation' 
                END as statut_attestation
            FROM `tabMouvement GNR` m
            LEFT JOIN `tabCustomer` c ON m.client = c.name
            WHERE m.date_mouvement BETWEEN %s AND %s
            AND m.docstatus = 1
            AND m.type_mouvement = 'Vente'
            AND m.client IS NOT NULL
            GROUP BY m.client, c.customer_name, c.custom_n_dossier_, c.custom_date_de_depot
            ORDER BY volume_total DESC
            LIMIT 10
        """, (from_date, to_date), as_dict=True)
        
        return {
            'success': True,
            'periode': f"{from_date} au {to_date}",
            'rapport_produits': rapport,
            'evolution_temporelle': evolution,
            'top_clients': top_clients,
            'resume': {
                'nb_produits': len(rapport),
                'volume_total': sum([p.quantite_totale for p in rapport]),
                'taxe_totale': sum([p.taxe_totale for p in rapport]),
                'taux_moyen_global': sum([p.taxe_totale for p in rapport]) / sum([p.quantite_totale for p in rapport]) if sum([p.quantite_totale for p in rapport]) > 0 else 0,
                'total_mouvements_suspects': sum([p.nb_taux_suspects for p in rapport]),
                'pourcentage_suspects': (sum([p.nb_taux_suspects for p in rapport]) / sum([p.nb_mouvements for p in rapport]) * 100) if sum([p.nb_mouvements for p in rapport]) > 0 else 0
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur rapport taux GNR: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def recalculer_montants_taxe(limite=500):
    """
    Recalcule les montants de taxe GNR pour tous les mouvements
    où montant_taxe_gnr ≠ quantite × taux_gnr
    """
    try:
        # Trouver les mouvements avec des écarts de calcul
        mouvements_incorrects = frappe.db.sql("""
            SELECT name, quantite, taux_gnr, montant_taxe_gnr,
                   (quantite * taux_gnr) as montant_calcule,
                   ABS((quantite * taux_gnr) - COALESCE(montant_taxe_gnr, 0)) as ecart
            FROM `tabMouvement GNR`
            WHERE docstatus = 1
            AND quantite > 0
            AND taux_gnr > 0
            AND ABS((quantite * taux_gnr) - COALESCE(montant_taxe_gnr, 0)) > 0.01
            ORDER BY ecart DESC
            LIMIT %s
        """, (limite,), as_dict=True)
        
        corriges = 0
        echecs = 0
        
        for mouvement in mouvements_incorrects:
            try:
                nouveau_montant = mouvement.quantite * mouvement.taux_gnr
                
                # Mettre à jour directement en base (plus rapide)
                frappe.db.set_value("Mouvement GNR", mouvement.name, 
                                  "montant_taxe_gnr", nouveau_montant)
                corriges += 1
                
            except Exception as e:
                frappe.log_error(f"Erreur recalcul montant {mouvement.name}: {str(e)}")
                echecs += 1
        
        frappe.db.commit()
        
        return {
            'success': True,
            'corriges': corriges,
            'echecs': echecs,
            'message': f"{corriges} montants de taxe recalculés, {echecs} échecs"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur recalcul montants taxe: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def detecter_anomalies_taux():
    """
    Détecte les anomalies dans les taux GNR en comparant avec l'historique
    """
    try:
        # Analyser les variations de taux par produit
        anomalies = frappe.db.sql("""
            WITH stats_produit AS (
                SELECT 
                    code_produit,
                    AVG(taux_gnr) as taux_moyen,
                    STDDEV(taux_gnr) as ecart_type,
                    MIN(taux_gnr) as taux_min,
                    MAX(taux_gnr) as taux_max,
                    COUNT(*) as nb_mouvements
                FROM `tabMouvement GNR`
                WHERE docstatus = 1 
                AND taux_gnr > 0
                AND date_mouvement >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                GROUP BY code_produit
                HAVING COUNT(*) >= 5  -- Au moins 5 mouvements pour avoir des stats
            )
            SELECT 
                m.name,
                m.code_produit,
                m.date_mouvement,
                m.taux_gnr,
                s.taux_moyen,
                s.ecart_type,
                s.taux_min,
                s.taux_max,
                -- Calculer le z-score (nombre d'écarts-types)
                CASE 
                    WHEN s.ecart_type > 0 
                    THEN ABS(m.taux_gnr - s.taux_moyen) / s.ecart_type
                    ELSE 0
                END as z_score,
                -- Classer l'anomalie
                CASE 
                    WHEN ABS(m.taux_gnr - s.taux_moyen) / s.ecart_type > 3 THEN 'CRITIQUE'
                    WHEN ABS(m.taux_gnr - s.taux_moyen) / s.ecart_type > 2 THEN 'ELEVEE'
                    WHEN ABS(m.taux_gnr - s.taux_moyen) / s.ecart_type > 1.5 THEN 'MODEREE'
                    ELSE 'NORMALE'
                END as niveau_anomalie
            FROM `tabMouvement GNR` m
            JOIN stats_produit s ON m.code_produit = s.code_produit
            WHERE m.docstatus = 1
            AND m.date_mouvement >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
            AND ABS(m.taux_gnr - s.taux_moyen) / s.ecart_type > 1.5  -- Seulement les anomalies
            ORDER BY z_score DESC
            LIMIT 100
        """, as_dict=True)
        
        # Grouper par niveau d'anomalie
        par_niveau = {}
        for anomalie in anomalies:
            niveau = anomalie.niveau_anomalie
            if niveau not in par_niveau:
                par_niveau[niveau] = []
            par_niveau[niveau].append(anomalie)
        
        return {
            'success': True,
            'anomalies': anomalies,
            'par_niveau': par_niveau,
            'resume': {
                'total_anomalies': len(anomalies),
                'critiques': len(par_niveau.get('CRITIQUE', [])),
                'elevees': len(par_niveau.get('ELEVEE', [])),
                'moderees': len(par_niveau.get('MODEREE', []))
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur détection anomalies: {str(e)}")
        return {'success': False, 'error': str(e)}