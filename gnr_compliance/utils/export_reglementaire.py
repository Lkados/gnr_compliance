# gnr_compliance/utils/export_simple.py
# Version simplifiée utilisant CSV et HTML

import frappe
from frappe.utils import getdate, flt, format_date, get_url
from datetime import datetime
import json
import csv
from io import StringIO

@frappe.whitelist()
def generer_arrete_trimestriel_simple(from_date, to_date):
    """Version simple de l'arrêté trimestriel en CSV"""
    try:
        # Récupérer les données
        mouvements = get_mouvements_gnr_periode(from_date, to_date)
        
        if not mouvements:
            return {
                "success": False,
                "message": "Aucun mouvement GNR trouvé pour cette période"
            }
        
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
        
        # Créer le contenu CSV
        output = StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # En-tête du document
        periode_text = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%B %Y')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B %Y')}"
        writer.writerow([f'ARRÊTÉ TRIMESTRIEL DE STOCK DÉTAILLÉ - {periode_text}'])
        writer.writerow(['Conformément à l\'arrêté du 28 juin 2001'])
        writer.writerow([])  # Ligne vide
        
        # En-têtes des colonnes
        headers = [
            "Code Produit", "Désignation", "Stock Début (hL)", 
            "Entrées (hL)", "Sorties (hL)", "Stock Fin (hL)",
            "Taux GNR (€/hL)", "Montant Taxe (€)"
        ]
        writer.writerow(headers)
        
        # Données
        total_taxe = 0
        for code_produit, produit in produits_data.items():
            stock_fin = produit['stock_debut'] + produit['entrees'] - produit['sorties']
            
            row = [
                code_produit,
                produit['designation'],
                f"{produit['stock_debut']:.3f}",
                f"{produit['entrees']:.3f}",
                f"{produit['sorties']:.3f}",
                f"{stock_fin:.3f}",
                f"{produit['taux_gnr']:.2f}",
                f"{produit['montant_taxe']:.2f}"
            ]
            writer.writerow(row)
            total_taxe += produit['montant_taxe']
        
        # Total
        writer.writerow([])
        writer.writerow(['', '', '', '', '', '', 'TOTAL TAXE GNR', f"{total_taxe:.2f}"])
        
        # Informations légales
        writer.writerow([])
        writer.writerow([f'Document généré le {datetime.now().strftime("%d/%m/%Y à %H:%M")}'])
        
        # Créer le fichier
        content = output.getvalue()
        output.close()
        
        periode_nom = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%Y_%m')}_à_{datetime.strptime(to_date, '%Y-%m-%d').strftime('%Y_%m')}"
        file_name = f"Arrete_Trimestriel_Stock_{periode_nom}.csv"
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": content.encode('utf-8'),
            "is_private": 0
        })
        file_doc.save()
        
        return {
            "file_url": file_doc.file_url,
            "file_name": file_name,
            "success": True,
            "message": f"Arrêté trimestriel généré - {len(produits_data)} produits, Total taxe: {total_taxe:.2f}€"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur génération arrêté simple: {str(e)}")
        return {
            "success": False,
            "message": f"Erreur: {str(e)}"
        }

@frappe.whitelist()
def generer_liste_clients_simple(from_date, to_date):
    """Version simple de la liste clients en CSV"""
    try:
        # Récupérer les données clients
        clients_data = get_clients_gnr_periode(from_date, to_date)
        
        if not clients_data:
            return {
                "success": False,
                "message": "Aucun client avec ventes GNR trouvé pour cette période"
            }
        
        # Créer le contenu CSV
        output = StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # En-tête du document
        periode_text = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%B %Y')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B %Y')}"
        writer.writerow([f'LISTE SEMESTRIELLE DES CLIENTS - {periode_text}'])
        writer.writerow(['Déclaration pour la Direction Générale des Douanes et Droits Indirects'])
        writer.writerow([])  # Ligne vide
        
        # En-têtes des colonnes
        headers = [
            "Code Client", "Nom/Raison Sociale", "SIRET",
            "Quantité Totale (hL)", "Montant HT (€)", "Montant Taxe GNR (€)"
        ]
        writer.writerow(headers)
        
        # Données
        total_quantite = 0
        total_ht = 0
        total_taxe = 0
        
        for client in clients_data:
            row = [
                client['code_client'],
                client['nom_client'],
                client['siret'] or '',
                f"{client['quantite_totale']:.3f}",
                f"{client['montant_ht']:.2f}",
                f"{client['montant_taxe']:.2f}"
            ]
            writer.writerow(row)
            total_quantite += client['quantite_totale']
            total_ht += client['montant_ht']
            total_taxe += client['montant_taxe']
        
        # Totaux
        writer.writerow([])
        writer.writerow(['', 'TOTAUX', '', f"{total_quantite:.3f}", f"{total_ht:.2f}", f"{total_taxe:.2f}"])
        
        # Informations légales
        writer.writerow([])
        writer.writerow(['Déclaration établie conformément au décret n°2001-387 du 3 mai 2001'])
        writer.writerow([f'Date d\'établissement: {datetime.now().strftime("%d/%m/%Y")}'])
        
        # Créer le fichier
        content = output.getvalue()
        output.close()
        
        periode_nom = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%Y_%m')}_à_{datetime.strptime(to_date, '%Y-%m-%d').strftime('%Y_%m')}"
        file_name = f"Liste_Clients_Semestrielle_{periode_nom}.csv"
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": content.encode('utf-8'),
            "is_private": 0
        })
        file_doc.save()
        
        return {
            "file_url": file_doc.file_url,
            "file_name": file_name,
            "success": True,
            "message": f"Liste clients générée - {len(clients_data)} clients, Total: {total_quantite:.2f}L"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur génération liste clients simple: {str(e)}")
        return {
            "success": False,
            "message": f"Erreur: {str(e)}"
        }

@frappe.whitelist()
def generer_export_html(from_date, to_date, type_export="arrete"):
    """Génère un export HTML stylé (alternative à Excel)"""
    try:
        if type_export == "arrete":
            data = get_data_for_arrete(from_date, to_date)
            html_content = generate_arrete_html(data, from_date, to_date)
            file_name = f"Arrete_Trimestriel_{from_date}_{to_date}.html"
        else:
            data = get_clients_gnr_periode(from_date, to_date)
            html_content = generate_clients_html(data, from_date, to_date)
            file_name = f"Liste_Clients_{from_date}_{to_date}.html"
        
        # Créer le fichier HTML
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": html_content.encode('utf-8'),
            "is_private": 0
        })
        file_doc.save()
        
        return {
            "file_url": file_doc.file_url,
            "file_name": file_name,
            "success": True,
            "message": "Export HTML généré avec succès"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur génération HTML: {str(e)}")
        return {
            "success": False,
            "message": f"Erreur: {str(e)}"
        }

def generate_arrete_html(produits_data, from_date, to_date):
    """Génère le HTML pour l'arrêté trimestriel"""
    periode_text = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%B %Y')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B %Y')}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Arrêté Trimestriel de Stock Détaillé</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ text-align: center; background: #1f4e79; color: white; padding: 15px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
            .number {{ text-align: right; }}
            .total {{ font-weight: bold; background-color: #e6f3ff; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>ARRÊTÉ TRIMESTRIEL DE STOCK DÉTAILLÉ</h1>
            <h2>{periode_text}</h2>
            <p>Conformément à l'arrêté du 28 juin 2001</p>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Code Produit</th>
                    <th>Désignation</th>
                    <th>Stock Début (hL)</th>
                    <th>Entrées (hL)</th>
                    <th>Sorties (hL)</th>
                    <th>Stock Fin (hL)</th>
                    <th>Taux GNR (€/hL)</th>
                    <th>Montant Taxe (€)</th>
                </tr>
            </thead>
            <tbody>
    """
    
    total_taxe = 0
    for code, produit in produits_data.items():
        stock_fin = produit['stock_debut'] + produit['entrees'] - produit['sorties']
        total_taxe += produit['montant_taxe']
        
        html += f"""
                <tr>
                    <td>{code}</td>
                    <td style="text-align: left;">{produit['designation']}</td>
                    <td class="number">{produit['stock_debut']:.3f}</td>
                    <td class="number">{produit['entrees']:.3f}</td>
                    <td class="number">{produit['sorties']:.3f}</td>
                    <td class="number">{stock_fin:.3f}</td>
                    <td class="number">{produit['taux_gnr']:.2f}</td>
                    <td class="number">{produit['montant_taxe']:.2f}</td>
                </tr>
        """
    
    html += f"""
            </tbody>
            <tfoot>
                <tr class="total">
                    <td colspan="7"><strong>TOTAL TAXE GNR</strong></td>
                    <td class="number"><strong>{total_taxe:.2f} €</strong></td>
                </tr>
            </tfoot>
        </table>
        
        <div class="footer">
            <p>Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
            <p><em>Ce document peut être imprimé ou sauvegardé au format PDF depuis votre navigateur</em></p>
        </div>
    </body>
    </html>
    """
    
    return html

def generate_clients_html(clients_data, from_date, to_date):
    """Génère le HTML pour la liste clients"""
    periode_text = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%B %Y')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B %Y')}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Liste Semestrielle des Clients</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ text-align: center; background: #1f4e79; color: white; padding: 15px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
            .number {{ text-align: right; }}
            .text {{ text-align: left; }}
            .total {{ font-weight: bold; background-color: #e6f3ff; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            .legal {{ margin-top: 30px; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #1f4e79; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>LISTE SEMESTRIELLE DES CLIENTS</h1>
            <h2>{periode_text}</h2>
            <p>Déclaration pour la Direction Générale des Douanes et Droits Indirects</p>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Code Client</th>
                    <th>Nom/Raison Sociale</th>
                    <th>SIRET</th>
                    <th>Quantité Totale (hL)</th>
                    <th>Montant HT (€)</th>
                    <th>Montant Taxe GNR (€)</th>
                </tr>
            </thead>
            <tbody>
    """
    
    total_quantite = 0
    total_ht = 0
    total_taxe = 0
    
    for client in clients_data:
        total_quantite += client['quantite_totale']
        total_ht += client['montant_ht']
        total_taxe += client['montant_taxe']
        
        html += f"""
                <tr>
                    <td>{client['code_client']}</td>
                    <td class="text">{client['nom_client']}</td>
                    <td>{client['siret'] or ''}</td>
                    <td class="number">{client['quantite_totale']:.3f}</td>
                    <td class="number">{client['montant_ht']:.2f}</td>
                    <td class="number">{client['montant_taxe']:.2f}</td>
                </tr>
        """
    
    html += f"""
            </tbody>
            <tfoot>
                <tr class="total">
                    <td colspan="3"><strong>TOTAUX</strong></td>
                    <td class="number"><strong>{total_quantite:.3f}</strong></td>
                    <td class="number"><strong>{total_ht:.2f} €</strong></td>
                    <td class="number"><strong>{total_taxe:.2f} €</strong></td>
                </tr>
            </tfoot>
        </table>
        
        <div class="legal">
            <h3>Informations Légales</h3>
            <p><strong>Déclaration établie conformément au décret n°2001-387 du 3 mai 2001</strong></p>
            <p>Cette liste doit être transmise semestriellement à la Direction Générale des Douanes et Droits Indirects.</p>
        </div>
        
        <div class="footer">
            <p>Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
            <p><em>Ce document peut être imprimé ou sauvegardé au format PDF depuis votre navigateur</em></p>
        </div>
    </body>
    </html>
    """
    
    return html

def get_data_for_arrete(from_date, to_date):
    """Récupère et groupe les données pour l'arrêté"""
    mouvements = get_mouvements_gnr_periode(from_date, to_date)
    
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
    
    return produits_data

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