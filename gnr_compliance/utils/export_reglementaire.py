# gnr_compliance/utils/export_reglementaire.py
# Générateurs d'exports aux formats réglementaires français

import frappe
from frappe.utils import getdate, flt
import xlsxwriter
from io import BytesIO
from datetime import datetime

@frappe.whitelist()
def generer_arrete_trimestriel(from_date, to_date, include_details=True):
    """
    Génère l'Arrêté Trimestriel de Stock Détaillé au format réglementaire
    
    Args:
        from_date: Date début (YYYY-MM-DD)
        to_date: Date fin (YYYY-MM-DD)
        include_details: Inclure les détails par produit
    
    Returns:
        dict: URL du fichier généré
    """
    try:
        # Récupérer les données des mouvements GNR
        mouvements = get_mouvements_gnr_periode(from_date, to_date)
        
        # Créer le fichier Excel
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # === FORMATS DE CELLULES ===
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        data_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.000'
        })
        
        text_format = workbook.add_format({
            'border': 1,
            'align': 'left'
        })
        
        currency_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00 €'
        })
        
        # === FEUILLE PRINCIPALE ===
        worksheet = workbook.add_worksheet('Arrêté Stock Détaillé')
        
        # En-tête du document
        periode_text = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%B %Y')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B %Y')}"
        
        worksheet.merge_range('A1:H1', f'ARRÊTÉ TRIMESTRIEL DE STOCK DÉTAILLÉ - {periode_text}', header_format)
        worksheet.merge_range('A2:H2', 'Conformément à l\'arrêté du 28 juin 2001', header_format)
        
        # En-têtes colonnes (ligne 4)
        headers = [
            'Code Produit',
            'Désignation',
            'Stock Début (hL)',
            'Entrées (hL)', 
            'Sorties (hL)',
            'Stock Fin (hL)',
            'Taux GNR (€/hL)',
            'Montant Taxe (€)'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(3, col, header, header_format)
            
        # Largeurs des colonnes
        column_widths = [15, 30, 15, 15, 15, 15, 15, 18]
        for i, width in enumerate(column_widths):
            worksheet.set_column(i, i, width)
        
        # === DONNÉES ===
        row = 4
        total_taxe = 0
        
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
                    'stock_fin': 0,
                    'taux_gnr': mouvement.taux_gnr or 0,
                    'montant_taxe': 0
                }
            
            if mouvement.type_mouvement in ['Achat', 'Entrée']:
                produits_data[code]['entrees'] += flt(mouvement.quantite)
            elif mouvement.type_mouvement in ['Vente', 'Sortie']:
                produits_data[code]['sorties'] += flt(mouvement.quantite)
            
            produits_data[code]['montant_taxe'] += flt(mouvement.montant_taxe_gnr or 0)
        
        # Écrire les données
        for code_produit, data in produits_data.items():
            # Calculer stock fin = stock début + entrées - sorties
            data['stock_fin'] = data['stock_debut'] + data['entrees'] - data['sorties']
            
            worksheet.write(row, 0, code_produit, text_format)
            worksheet.write(row, 1, data['designation'], text_format)
            worksheet.write(row, 2, data['stock_debut'], data_format)
            worksheet.write(row, 3, data['entrees'], data_format)
            worksheet.write(row, 4, data['sorties'], data_format)
            worksheet.write(row, 5, data['stock_fin'], data_format)
            worksheet.write(row, 6, data['taux_gnr'], currency_format)
            worksheet.write(row, 7, data['montant_taxe'], currency_format)
            
            total_taxe += data['montant_taxe']
            row += 1
        
        # Total final
        worksheet.merge_range(row + 1, 0, row + 1, 6, 'TOTAL TAXE GNR', header_format)
        worksheet.write(row + 1, 7, total_taxe, currency_format)
        
        # Signature et date
        worksheet.write(row + 4, 5, 'Date et signature:', text_format)
        worksheet.write(row + 5, 5, datetime.now().strftime('%d/%m/%Y'), text_format)
        
        workbook.close()
        output.seek(0)
        
        # Créer le fichier
        periode_nom = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%Y %B')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B')}"
        file_name = f"TIPAccEne Arrêté Trimestriel de Stock Détaillé {periode_nom}.xlsx"
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": output.getvalue()
        })
        file_doc.save()
        
        return {"file_url": file_doc.file_url, "file_name": file_name}
        
    except Exception as e:
        frappe.throw(f"Erreur génération arrêté trimestriel: {str(e)}")

@frappe.whitelist()
def generer_liste_semestrielle_clients(from_date, to_date):
    """
    Génère la Liste Semestrielle des Clients pour la Douane
    
    Args:
        from_date: Date début semestre
        to_date: Date fin semestre
    
    Returns:
        dict: URL du fichier généré
    """
    try:
        # Récupérer les données clients avec ventes GNR
        clients_data = get_clients_gnr_periode(from_date, to_date)
        
        # Créer le fichier Excel
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # === FORMATS ===
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        data_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.000'
        })
        
        text_format = workbook.add_format({
            'border': 1,
            'align': 'left'
        })
        
        currency_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00 €'
        })
        
        # === FEUILLE CLIENTS ===
        worksheet = workbook.add_worksheet('Liste Clients Semestrielle')
        
        # En-tête
        periode_text = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%B %Y')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B %Y')}"
        worksheet.merge_range('A1:F1', f'LISTE SEMESTRIELLE DES CLIENTS - {periode_text}', header_format)
        worksheet.merge_range('A2:F2', 'Déclaration pour la Direction Générale des Douanes et Droits Indirects', header_format)
        
        # En-têtes colonnes
        headers = [
            'Code Client',
            'Nom/Raison Sociale',
            'SIRET',
            'Quantité Totale (hL)',
            'Montant HT (€)',
            'Montant Taxe GNR (€)'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(3, col, header, header_format)
        
        # Largeurs colonnes
        column_widths = [15, 35, 20, 18, 18, 18]
        for i, width in enumerate(column_widths):
            worksheet.set_column(i, i, width)
        
        # === DONNÉES CLIENTS ===
        row = 4
        total_quantite = 0
        total_ht = 0
        total_taxe = 0
        
        for client in clients_data:
            worksheet.write(row, 0, client['code_client'], text_format)
            worksheet.write(row, 1, client['nom_client'], text_format)
            worksheet.write(row, 2, client['siret'] or '', text_format)
            worksheet.write(row, 3, client['quantite_totale'], data_format)
            worksheet.write(row, 4, client['montant_ht'], currency_format)
            worksheet.write(row, 5, client['montant_taxe'], currency_format)
            
            total_quantite += client['quantite_totale']
            total_ht += client['montant_ht']
            total_taxe += client['montant_taxe']
            row += 1
        
        # Totaux
        worksheet.merge_range(row + 1, 0, row + 1, 2, 'TOTAUX', header_format)
        worksheet.write(row + 1, 3, total_quantite, data_format)
        worksheet.write(row + 1, 4, total_ht, currency_format)
        worksheet.write(row + 1, 5, total_taxe, currency_format)
        
        # Informations légales
        worksheet.write(row + 4, 0, 'Déclaration établie conformément au décret n°2001-387 du 3 mai 2001', text_format)
        worksheet.write(row + 5, 0, f'Date d\'établissement: {datetime.now().strftime("%d/%m/%Y")}', text_format)
        
        workbook.close()
        output.seek(0)
        
        # Créer le fichier
        periode_nom = f"{datetime.strptime(from_date, '%Y-%m-%d').strftime('%Y %B')} à {datetime.strptime(to_date, '%Y-%m-%d').strftime('%B')}"
        file_name = f"TIPAccEne Liste Semestrielle des Clients Douane {periode_nom}.xlsx"
        
        file_doc = frappe.get_doc({
            "doctype": "File", 
            "file_name": file_name,
            "content": output.getvalue()
        })
        file_doc.save()
        
        return {"file_url": file_doc.file_url, "file_name": file_name}
        
    except Exception as e:
        frappe.throw(f"Erreur génération liste clients: {str(e)}")

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
            SUM(m.quantite * m.prix_unitaire) as montant_ht,
            SUM(m.montant_taxe_gnr) as montant_taxe
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