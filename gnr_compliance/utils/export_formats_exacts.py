# gnr_compliance/utils/export_formats_exacts.py
# Reproduction exacte des formats Excel originaux

import frappe
from frappe.utils import getdate, flt, format_date
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from io import BytesIO

@frappe.whitelist()
def generer_declaration_trimestrielle_exacte(from_date, to_date):
    """
    Génère la Déclaration Trimestrielle au format exact
    Comptabilité Matière - Gasoil Non Routier
    """
    try:
        # Récupérer les informations de la société
        company = frappe.get_single("Global Defaults").default_company
        company_doc = frappe.get_doc("Company", company) if company else None
        
        # Créer le classeur
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Comptabilité Matière GNR"
        
        # === STYLES ===
        title_font = Font(name="Arial", size=14, bold=True)
        header_font = Font(name="Arial", size=11, bold=True)
        normal_font = Font(name="Arial", size=10)
        
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")
        
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
        # === EN-TÊTE ===
        # Ligne 1 : Titre principal
        ws.merge_cells('A1:K1')
        ws['A1'] = "Comptabilité Matière - Gasoil Non Routier"
        ws['A1'].font = title_font
        ws['A1'].alignment = center_align
        
        # Ligne 3 : Informations société
        ws['A3'] = f"Société : {company_doc.company_name if company_doc else 'ETS STEPHANE JOSSEAUME'}"
        ws['A3'].font = header_font
        
        # Ligne 4 : Numéro d'autorisation
        numero_autorisation = frappe.get_single_value("GNR Settings", "numero_autorisation") or "08/2024/AMIENS"
        ws['A4'] = f"Numéro d'autorisation : {numero_autorisation}"
        ws['A4'].font = normal_font
        
        # Ligne 5 : Période
        periode_text = generer_texte_periode_trimestre(from_date, to_date)
        ws['A5'] = periode_text
        ws['A5'].font = header_font
        
        # Ligne 7 : Sous-titre
        ws['A7'] = "Volume réel en Litres"
        ws['A7'].font = header_font
        
        # === EN-TÊTES COLONNES (Ligne 8) ===
        headers = [
            "Date", "Stock Initial", "Entrées", "Sorties", "Stock Final", 
            "N° BL", "Volume", "AGRICOLE /\nFORESTIER", "Volume", 
            "Sans\nAttestation", "Volume"
        ]
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=8, column=col, value=header)
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border
        
        # === DONNÉES ===
        mouvements_journaliers = calculer_mouvements_journaliers(from_date, to_date)
        
        row = 9
        for mouvement in mouvements_journaliers:
            # Date
            ws.cell(row=row, column=1, value=mouvement['date_format']).border = thin_border
            
            # Stock Initial
            ws.cell(row=row, column=2, value=mouvement['stock_initial']).border = thin_border
            ws.cell(row=row, column=2).number_format = '#,##0'
            
            # Entrées
            ws.cell(row=row, column=3, value=mouvement['entrees']).border = thin_border
            ws.cell(row=row, column=3).number_format = '#,##0'
            
            # Sorties
            ws.cell(row=row, column=4, value=mouvement['sorties']).border = thin_border
            ws.cell(row=row, column=4).number_format = '#,##0'
            
            # Stock Final
            ws.cell(row=row, column=5, value=mouvement['stock_final']).border = thin_border
            ws.cell(row=row, column=5).number_format = '#,##0'
            
            # N° BL (vide pour l'instant)
            ws.cell(row=row, column=6, value="").border = thin_border
            
            # Volume (copie des sorties)
            ws.cell(row=row, column=7, value=mouvement['sorties']).border = thin_border
            ws.cell(row=row, column=7).number_format = '#,##0'
            
            # AGRICOLE/FORESTIER (avec attestation - tarif 3,86)
            ws.cell(row=row, column=8, value=mouvement['volume_agricole']).border = thin_border
            ws.cell(row=row, column=8).number_format = '#,##0'
            
            # Volume agricole (répétition pour clarté)
            ws.cell(row=row, column=9, value=mouvement['volume_agricole']).border = thin_border
            ws.cell(row=row, column=9).number_format = '#,##0'
            
            # Sans Attestation (tarif 24,81)
            ws.cell(row=row, column=10, value=mouvement['volume_sans_attestation']).border = thin_border
            ws.cell(row=row, column=10).number_format = '#,##0'
            
            # Volume sans attestation (répétition)
            ws.cell(row=row, column=11, value=mouvement['volume_sans_attestation']).border = thin_border
            ws.cell(row=row, column=11).number_format = '#,##0'
            
            row += 1
        
        # === AJUSTEMENTS COLONNES ===
        column_widths = [12, 12, 10, 10, 12, 8, 10, 12, 10, 12, 10]
        for i, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = width
        
        # === SAUVEGARDE ===
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        # Nom de fichier exact
        trimestre_text = determiner_trimestre_text(from_date, to_date)
        file_name = f"TIPAccEne Arrêté Trimestriel de Stock Détaillé {trimestre_text}.xlsx"
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": output.getvalue(),
            "is_private": 0
        })
        file_doc.save()
        
        return {
            "success": True,
            "file_url": file_doc.file_url,
            "file_name": file_name,
            "message": f"Déclaration trimestrielle générée - {len(mouvements_journaliers)} jours de mouvements"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur génération déclaration trimestrielle: {str(e)}")
        return {"success": False, "message": f"Erreur: {str(e)}"}

@frappe.whitelist()
def generer_liste_semestrielle_exacte(from_date, to_date):
    """
    Génère la Liste Semestrielle des Clients au format exact
    """
    try:
        # Récupérer les données clients avec distinction attestation
        clients_data = get_clients_avec_attestation(from_date, to_date)
        
        if not clients_data:
            return {"success": False, "message": "Aucun client trouvé pour cette période"}
        
        # Créer le classeur
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Liste Clients Semestrielle"
        
        # === STYLES ===
        header_font = Font(name="Arial", size=11, bold=True)
        normal_font = Font(name="Arial", size=10)
        
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
        # === EN-TÊTES COLONNES ===
        headers = [
            ["Informations distributeur autorisé ou fournisseur", "", "Informations client", "", "Données carburant GNR", ""],
            ["Raison sociale", "SIREN", "Raison sociale du client", "SIREN du client", 
             "Volumes (en hL) de GNR livrés au client au cours du dernier semestre civil écoulé", 
             "Tarif d'accise appliqué (en euro par hectolitres)"]
        ]
        
        # Première ligne d'en-têtes (groupements)
        ws.merge_cells('A1:B1')
        ws['A1'] = headers[0][0]
        ws['A1'].font = header_font
        ws['A1'].alignment = center_align
        ws['A1'].border = thin_border
        
        ws.merge_cells('C1:D1') 
        ws['C1'] = headers[0][2]
        ws['C1'].font = header_font
        ws['C1'].alignment = center_align
        ws['C1'].border = thin_border
        
        ws.merge_cells('E1:F1')
        ws['E1'] = headers[0][4]
        ws['E1'].font = header_font
        ws['E1'].alignment = center_align
        ws['E1'].border = thin_border
        
        # Deuxième ligne d'en-têtes (détails)
        for col, header in enumerate(headers[1], 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border
        
        # === DONNÉES CLIENTS ===
        company_name = frappe.get_single_value("Global Defaults", "default_company") or "ETS STEPHANE JOSSEAUME"
        company_siren = ""  # À récupérer depuis les paramètres société
        
        row = 3
        for client in clients_data:
            # Raison sociale distributeur
            ws.cell(row=row, column=1, value=company_name).border = thin_border
            
            # SIREN distributeur
            ws.cell(row=row, column=2, value=company_siren).border = thin_border
            
            # Raison sociale client
            ws.cell(row=row, column=3, value=client['nom_client']).border = thin_border
            
            # SIREN client
            ws.cell(row=row, column=4, value=client['siren'] or "").border = thin_border
            
            # Volume en hL (conversion de L vers hL)
            volume_hl = client['quantite_totale'] / 100
            ws.cell(row=row, column=5, value=volume_hl).border = thin_border
            ws.cell(row=row, column=5).number_format = '#,##0.00'
            
            # Tarif d'accise (selon attestation)
            tarif = 3.86 if client['avec_attestation'] else 24.81
            ws.cell(row=row, column=6, value=tarif).border = thin_border
            ws.cell(row=row, column=6).number_format = '#,##0.00'
            
            row += 1
        
        # === AJUSTEMENTS COLONNES ===
        column_widths = [25, 15, 30, 15, 35, 25]
        for i, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = width
        
        # === SAUVEGARDE ===
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        # Nom de fichier exact
        periode_text = generer_texte_periode_semestre(from_date, to_date)
        file_name = f"TIPAccEne Liste Semestrielle des Clients Douane {periode_text}.xlsx"
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": output.getvalue(),
            "is_private": 0
        })
        file_doc.save()
        
        return {
            "success": True,
            "file_url": file_doc.file_url,
            "file_name": file_name,
            "message": f"Liste semestrielle générée - {len(clients_data)} clients"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur génération liste semestrielle: {str(e)}")
        return {"success": False, "message": f"Erreur: {str(e)}"}

def calculer_mouvements_journaliers(from_date, to_date):
    """Calcule les mouvements jour par jour avec stocks"""
    
    # Récupérer tous les mouvements de la période avec l'info attestation du client
    # Un client a une attestation si custom_n_dossier_ ET custom_date_de_depot sont remplis
    mouvements = frappe.db.sql("""
        SELECT 
            DATE(m.date_mouvement) as date_mouvement,
            SUM(CASE WHEN m.type_mouvement IN ('Achat', 'Entrée') THEN m.quantite ELSE 0 END) as entrees,
            SUM(CASE WHEN m.type_mouvement IN ('Vente', 'Sortie') THEN m.quantite ELSE 0 END) as sorties,
            SUM(CASE WHEN m.type_mouvement = 'Vente' AND (c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL) THEN m.quantite ELSE 0 END) as volume_agricole,
            SUM(CASE WHEN m.type_mouvement = 'Vente' AND (c.custom_n_dossier_ IS NULL OR c.custom_n_dossier_ = '' OR c.custom_date_de_depot IS NULL) THEN m.quantite ELSE 0 END) as volume_sans_attestation
        FROM `tabMouvement GNR` m
        LEFT JOIN `tabCustomer` c ON m.client = c.name
        WHERE m.date_mouvement BETWEEN %s AND %s
        AND m.docstatus = 1
        GROUP BY DATE(m.date_mouvement)
        ORDER BY DATE(m.date_mouvement)
    """, (from_date, to_date), as_dict=True)
    
    # Calculer le stock initial (avant la période)
    stock_initial = frappe.db.sql("""
        SELECT COALESCE(SUM(
            CASE 
                WHEN type_mouvement IN ('Achat', 'Entrée') THEN quantite
                WHEN type_mouvement IN ('Vente', 'Sortie') THEN -quantite
                ELSE 0
            END
        ), 0) as stock
        FROM `tabMouvement GNR`
        WHERE date_mouvement < %s
        AND docstatus = 1
    """, (from_date,))[0][0] or 0
    
    # Construire les données jour par jour
    resultats = []
    stock_courant = stock_initial
    
    # Créer toutes les dates de la période
    current_date = datetime.strptime(from_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
    
    mouvements_dict = {m.date_mouvement: m for m in mouvements}
    
    while current_date <= end_date:
        mouvement = mouvements_dict.get(current_date)
        
        if mouvement:
            entrees = int(mouvement.entrees or 0)
            sorties = int(mouvement.sorties or 0)
            volume_agricole = int(mouvement.volume_agricole or 0)
            volume_sans_attestation = int(mouvement.volume_sans_attestation or 0)
        else:
            entrees = sorties = volume_agricole = volume_sans_attestation = 0
        
        stock_initial_jour = int(stock_courant)
        stock_courant += entrees - sorties
        stock_final_jour = int(stock_courant)
        
        # Format de date comme dans l'exemple : "2-janv."
        date_format = format_date_french(current_date)
        
        resultats.append({
            'date_format': date_format,
            'stock_initial': stock_initial_jour,
            'entrees': entrees,
            'sorties': sorties,
            'stock_final': stock_final_jour,
            'volume_agricole': volume_agricole,
            'volume_sans_attestation': volume_sans_attestation
        })
        
        current_date += timedelta(days=1)
    
    return resultats

def get_clients_avec_attestation(from_date, to_date):
    """Récupère les clients avec distinction attestation/sans attestation selon les champs dossier et date de dépôt"""
    return frappe.db.sql("""
        SELECT 
            m.client as code_client,
            c.customer_name as nom_client,
            c.siret,
            SUM(m.quantite) as quantite_totale,
            CASE 
                WHEN c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL 
                THEN 1 
                ELSE 0 
            END as avec_attestation,
            c.custom_n_dossier_ as numero_dossier,
            c.custom_date_de_depot as date_depot
        FROM `tabMouvement GNR` m
        LEFT JOIN `tabCustomer` c ON m.client = c.name
        WHERE m.date_mouvement BETWEEN %s AND %s
        AND m.docstatus = 1
        AND m.type_mouvement = 'Vente'
        AND m.client IS NOT NULL
        GROUP BY m.client, c.customer_name, c.siret, c.custom_n_dossier_, c.custom_date_de_depot
        HAVING SUM(m.quantite) > 0
        ORDER BY c.customer_name
    """, (from_date, to_date), as_dict=True)

def format_date_french(date_obj):
    """Formate la date en français comme '2-janv.'"""
    mois_francais = {
        1: 'janv.', 2: 'févr.', 3: 'mars', 4: 'avr.', 5: 'mai', 6: 'juin',
        7: 'juil.', 8: 'août', 9: 'sept.', 10: 'oct.', 11: 'nov.', 12: 'déc.'
    }
    return f"{date_obj.day}-{mois_francais[date_obj.month]}"

def generer_texte_periode_trimestre(from_date, to_date):
    """Génère le texte de période pour le trimestre"""
    start = datetime.strptime(from_date, '%Y-%m-%d')
    end = datetime.strptime(to_date, '%Y-%m-%d')
    
    # Déterminer le trimestre
    if start.month <= 3:
        return f"1er Trimestre {start.year} (Janvier - Février - Mars)"
    elif start.month <= 6:
        return f"2ème Trimestre {start.year} (Avril - Mai - Juin)"
    elif start.month <= 9:
        return f"3ème Trimestre {start.year} (Juillet - Août - Septembre)"
    else:
        return f"4ème Trimestre {start.year} (Octobre - Novembre - Décembre)"

def generer_texte_periode_semestre(from_date, to_date):
    """Génère le texte de période pour le semestre"""
    start = datetime.strptime(from_date, '%Y-%m-%d')
    end = datetime.strptime(to_date, '%Y-%m-%d')
    
    if start.month <= 6:
        return f"{start.year} Janvier à Juin"
    else:
        return f"{start.year} Juillet à Décembre"

def determiner_trimestre_text(from_date, to_date):
    """Détermine le texte exact pour le nom de fichier"""
    start = datetime.strptime(from_date, '%Y-%m-%d')
    end = datetime.strptime(to_date, '%Y-%m-%d')
    
    if start.month <= 3:
        return f"{start.year} Janvier à Mars"
    elif start.month <= 6:
        return f"{start.year} Avril à Juin"
    elif start.month <= 9:
        return f"{start.year} Juillet à Septembre"
    else:
        return f"{start.year} Octobre à Décembre"