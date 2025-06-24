# gnr_compliance/utils/export_simple.py
# Version simplifiée utilisant les outils natifs Frappe

import frappe
from frappe.utils import getdate, flt, format_date
from frappe.utils.data import get_link_to_form
from datetime import datetime

@frappe.whitelist()
def generer_arrete_trimestriel_simple(from_date, to_date):
    """Version simple de l'arrêté trimestriel"""
    try:
        # Récupérer les données
        mouvements = get_mouvements_gnr_periode(from_date, to_date)
        
        # Préparer les données pour l'export
        data = []
        headers = [
            "Code Produit", "Désignation", "Stock Début (hL)", 
            "Entrées (hL)", "Sorties (hL)", "Stock Fin (hL)",
            "Taux GNR (€/hL)", "Montant Taxe (€)"
        ]
        
        # Grouper par produit
        produits_data = {}
        for mouvement in mouvements:
            code = mouvement.code_produit
            if code not in produits_data:
                produits_data[code] = {
                    'designation': frappe.get_value('Item', code, 'item_name') or code,
                    'stock_debut': 0,
                    'entrees': 0,
                    'sorties': 0,
                    'taux_gnr': mouvement.taux_gnr or 0,
                    'montant_taxe': 0
                }
            
            if mouvement.type_mouvement in ['Achat', 'Entrée']:
                produits_data[code]['entrees'] += flt(mouvement.quantite)
            elif mouvement.type_mouvement in ['Vente', 'Sortie']:
                produits_data[code]['sorties'] += flt(mouvement.quantite)
            
            produits_data[code]['montant_taxe'] += flt(mouvement.montant_taxe_gnr or 0)
        
        # Construire les données
        total_taxe = 0
        for code_produit, produit in produits_data.items():
            stock_fin = produit['stock_debut'] + produit['entrees'] - produit['sorties']
            
            data.append([
                code_produit,
                produit['designation'],
                produit['stock_debut'],
                produit['entrees'],
                produit['sorties'],
                stock_fin,
                produit['taux_gnr'],
                produit['montant_taxe']
            ])
            total_taxe += produit['montant_taxe']
        
        # Ajouter la ligne de total
        data.append([
            "", "", "", "", "", "", "TOTAL TAXE GNR", total_taxe
        ])
        
        # Générer le fichier avec l'outil Frappe
        from frappe.utils.xlutils import make_ods
        
        periode_text = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%B %Y')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B %Y')}"
        
        file_content = make_ods(data, headers, 
                              f"Arrêté Trimestriel de Stock Détaillé - {periode_text}")
        
        # Créer le fichier
        file_name = f"Arrete_Trimestriel_{from_date}_{to_date}.ods"
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": file_content
        })
        file_doc.save()
        
        return {
            "file_url": file_doc.file_url,
            "file_name": file_name,
            "message": f"Arrêté trimestriel généré - {len(data)-1} produits, Total taxe: {total_taxe}€"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur génération arrêté simple: {str(e)}")
        frappe.throw(f"Erreur: {str(e)}")

@frappe.whitelist()
def generer_liste_clients_simple(from_date, to_date):
    """Version simple de la liste clients"""
    try:
        # Récupérer les données clients
        clients_data = get_clients_gnr_periode(from_date, to_date)
        
        # Préparer les données
        headers = [
            "Code Client", "Nom/Raison Sociale", "SIRET",
            "Quantité Totale (hL)", "Montant HT (€)", "Montant Taxe GNR (€)"
        ]
        
        data = []
        total_quantite = 0
        total_ht = 0
        total_taxe = 0
        
        for client in clients_data:
            data.append([
                client['code_client'],
                client['nom_client'],
                client['siret'] or '',
                client['quantite_totale'],
                client['montant_ht'],
                client['montant_taxe']
            ])
            total_quantite += client['quantite_totale']
            total_ht += client['montant_ht']
            total_taxe += client['montant_taxe']
        
        # Ligne totaux
        data.append([
            "", "TOTAUX", "", total_quantite, total_ht, total_taxe
        ])
        
        # Générer le fichier
        from frappe.utils.xlutils import make_ods
        
        periode_text = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%B %Y')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B %Y')}"
        
        file_content = make_ods(data, headers,
                              f"Liste Semestrielle des Clients - {periode_text}")
        
        # Créer le fichier
        file_name = f"Liste_Clients_{from_date}_{to_date}.ods"
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": file_content
        })
        file_doc.save()
        
        return {
            "file_url": file_doc.file_url,
            "file_name": file_name,
            "message": f"Liste clients générée - {len(data)-1} clients, Total: {total_quantite}L"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur génération liste clients simple: {str(e)}")
        frappe.throw(f"Erreur: {str(e)}")

def get_mouvements_gnr_periode(from_date, to_date):
    """Récupère les mouvements GNR pour une période"""
    return frappe.db.sql("""
        SELECT 
            code_produit,
            type_mouvement,
            quantite,
            taux_gnr,
            montant_taxe_gnr
        FROM `tabMouvement GNR`
        WHERE date_mouvement BETWEEN %s AND %s
        AND docstatus = 1
        ORDER BY code_produit, date_mouvement
    """, (from_date, to_date), as_dict=True)

def get_clients_gnr_periode(from_date, to_date):
    """Récupère les données clients avec ventes GNR pour une période"""
    return frappe.db.sql("""
        SELECT 
            m.client as code_client,
            c.customer_name as nom_client,
            c.siret,
            SUM(m.quantite) as quantite_totale,
            SUM(m.quantite * COALESCE(m.prix_unitaire, 0)) as montant_ht,
            SUM(COALESCE(m.montant_taxe_gnr, 0)) as montant_taxe
        FROM `tabMouvement GNR` m
        LEFT JOIN `tabCustomer` c ON m.client = c.name
        WHERE m.date_mouvement BETWEEN %s AND %s
        AND m.docstatus = 1
        AND m.type_mouvement = 'Vente'
        AND m.client IS NOT NULL
        GROUP BY m.client
        HAVING SUM(m.quantite) > 0
        ORDER BY SUM(m.quantite) DESC
    """, (from_date, to_date), as_dict=True)