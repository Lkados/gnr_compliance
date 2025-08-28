# gnr_compliance/api.py
import frappe
from frappe import _
from io import BytesIO

@frappe.whitelist()
def generate_export(export_format, from_date, to_date, periode_type="Trimestrielle", inclure_details=False):
    """API pour génération d'exports GNR dans différents formats"""
    
    # Récupérer les données selon les filtres
    data = get_gnr_data(from_date, to_date, periode_type)
    
    if "Excel" in export_format:
        return generate_excel_export(data, from_date, to_date, inclure_details)
    else:
        frappe.throw(_("Format d'export non supporté: {0}").format(export_format))

def generate_excel_export(data, from_date, to_date, inclure_details):
    """Génération export Excel format arrêté trimestriel"""
    import xlsxwriter
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # Feuille principale
    worksheet = workbook.add_worksheet('Arrêté Stock Détaillé')
    
    # Styles
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#1f4e79',
        'font_color': 'white',
        'align': 'center',
        'valign': 'vcenter',
        'border': 1
    })
    
    # En-tête avec informations réglementaires
    worksheet.merge_range('A1:G1', f'ARRÊTÉ DE STOCK DÉTAILLÉ - Période: {from_date} au {to_date}', header_format)
    
    # Headers de colonnes
    headers = [
        'Code Produit', 'Désignation', 'Stock Début (hL)', 
        'Entrées (hL)', 'Sorties (hL)', 'Stock Fin (hL)', 
        'Taux GNR (€/hL)', 'Montant Taxe (€)'
    ]
    
    for col, header in enumerate(headers):
        worksheet.write(2, col, header, header_format)
    
    # Données
    row = 3
    total_taxe = 0
    
    for item in data:
        worksheet.write(row, 0, item.get('code_produit', ''))
        worksheet.write(row, 1, item.get('designation', ''))
        worksheet.write(row, 2, item.get('stock_debut', 0))
        worksheet.write(row, 3, item.get('entrees', 0))
        worksheet.write(row, 4, item.get('sorties', 0))
        worksheet.write(row, 5, item.get('stock_fin', 0))
        worksheet.write(row, 6, item.get('taux_gnr', 0))
        worksheet.write(row, 7, item.get('montant_taxe', 0))
        
        total_taxe += item.get('montant_taxe', 0)
        row += 1
    
    # Total
    worksheet.write(row + 1, 6, 'TOTAL TAXE:', header_format)
    worksheet.write(row + 1, 7, total_taxe, header_format)
    
    # Feuille détails clients si demandée
    if inclure_details:
        clients_data = get_clients_data_for_period(from_date, to_date)
        clients_sheet = workbook.add_worksheet('Liste Clients Semestrielle')
        
        client_headers = ['Code Client', 'Nom Client', 'SIRET', 'Quantité (hL)', 'Montant HT (€)']
        for col, header in enumerate(client_headers):
            clients_sheet.write(0, col, header, header_format)
        
        for idx, client in enumerate(clients_data, 1):
            clients_sheet.write(idx, 0, client.get('code_client', ''))
            clients_sheet.write(idx, 1, client.get('nom_client', ''))
            clients_sheet.write(idx, 2, client.get('siret', ''))
            clients_sheet.write(idx, 3, client.get('quantite_totale', 0))
            clients_sheet.write(idx, 4, client.get('montant_ht', 0))
    
    workbook.close()
    output.seek(0)
    
    # Créer fichier
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": f"Arrete_GNR_{from_date}_{to_date}.xlsx",
        "content": output.getvalue()
    })
    file_doc.save()
    
    return {"file_url": file_doc.file_url}

def get_clients_data_for_period(from_date, to_date):
    """Récupération des données clients pour la période"""
    return frappe.db.sql("""
        SELECT 
            c.name as code_client,
            c.customer_name as nom_client,
            c.tax_id as siret,
            SUM(m.quantite) as quantite_totale,
            SUM(m.quantite * m.prix_unitaire) as montant_ht
        FROM `tabMouvement GNR` m
        LEFT JOIN `tabCustomer` c ON m.client = c.name
        WHERE m.date_mouvement BETWEEN %s AND %s
        AND m.docstatus = 1
        AND m.type_mouvement = 'Vente'
        GROUP BY m.client
        ORDER BY quantite_totale DESC
    """, (from_date, to_date), as_dict=True)

def get_gnr_data(from_date, to_date, periode_type):
    """Récupération des données GNR pour la période"""
    return frappe.db.sql("""
        SELECT 
            m.code_produit,
            i.item_name as designation,
            SUM(CASE WHEN m.type_mouvement IN ('Achat', 'Entrée') THEN m.quantite ELSE 0 END) as entrees,
            SUM(CASE WHEN m.type_mouvement IN ('Vente', 'Sortie') THEN m.quantite ELSE 0 END) as sorties,
            m.taux_gnr,
            SUM(m.montant_taxe_gnr) as montant_taxe
        FROM `tabMouvement GNR` m
        LEFT JOIN `tabItem` i ON m.code_produit = i.item_code
        WHERE m.date_mouvement BETWEEN %s AND %s
        AND m.docstatus = 1
        GROUP BY m.code_produit, m.taux_gnr
        ORDER BY m.code_produit
    """, (from_date, to_date), as_dict=True)