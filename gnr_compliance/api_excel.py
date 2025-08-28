"""
API endpoints pour la génération des fichiers Excel GNR avec formats exacts
"""

import frappe
from frappe import _
from frappe.utils import today, add_days, add_months, getdate
from datetime import datetime
import calendar
from gnr_compliance.utils.excel_generators import (
    generate_arrete_trimestriel, 
    generate_liste_clients
)

@frappe.whitelist()
def download_arrete_trimestriel(period_start=None, period_end=None, quarter=None, year=None):
    """
    Télécharger l'arrêté trimestriel de stock au format Excel exact
    
    Args:
        period_start: Date de début (YYYY-MM-DD) 
        period_end: Date de fin (YYYY-MM-DD)
        quarter: Trimestre (1-4) 
        year: Année
    """
    try:
        # Si trimestre et année fournis, calculer les dates
        if quarter and year:
            quarter = int(quarter)
            year = int(year)
            
            if quarter == 1:
                period_start = f"{year}-01-01"
                period_end = f"{year}-03-31"
            elif quarter == 2:
                period_start = f"{year}-04-01" 
                period_end = f"{year}-06-30"
            elif quarter == 3:
                period_start = f"{year}-07-01"
                period_end = f"{year}-09-30"
            elif quarter == 4:
                period_start = f"{year}-10-01"
                period_end = f"{year}-12-31"
        
        # Valeurs par défaut si pas de paramètres
        if not period_start or not period_end:
            current_date = getdate(today())
            current_quarter = (current_date.month - 1) // 3 + 1
            current_year = current_date.year
            
            if current_quarter == 1:
                period_start = f"{current_year}-01-01"
                period_end = f"{current_year}-03-31"
            elif current_quarter == 2:
                period_start = f"{current_year}-04-01"
                period_end = f"{current_year}-06-30"
            elif current_quarter == 3:
                period_start = f"{current_year}-07-01"
                period_end = f"{current_year}-09-30"
            else:
                period_start = f"{current_year}-10-01"
                period_end = f"{current_year}-12-31"
        
        # Générer le fichier Excel
        excel_data = generate_arrete_trimestriel(period_start, period_end)
        
        # Nom du fichier basé sur les dates
        start_date = datetime.strptime(period_start, '%Y-%m-%d')
        end_date = datetime.strptime(period_end, '%Y-%m-%d')
        
        company = frappe.defaults.get_user_default("Company") or frappe.get_all("Company", limit=1)[0].name
        
        quarter_names = {
            1: "Janvier à Mars",
            2: "Avril à Juin", 
            3: "Juillet à Septembre",
            4: "Octobre à Décembre"
        }
        
        quarter_num = (start_date.month - 1) // 3 + 1
        quarter_text = quarter_names[quarter_num]
        
        filename = f"TIPAccEne - Arrêté Trimestriel de Stock - Détaillé - {start_date.year} {quarter_text}.xlsx"
        
        # Retourner le fichier pour téléchargement
        frappe.response.update({
            "type": "download",
            "filecontent": excel_data,
            "filename": filename
        })
        
    except Exception as e:
        frappe.throw(_("Erreur lors de la génération de l'arrêté trimestriel: {0}").format(str(e)))


@frappe.whitelist()
def download_liste_clients(period_start=None, period_end=None, semester=None, year=None):
    """
    Télécharger la liste semestrielle des clients au format Excel exact
    
    Args:
        period_start: Date de début (YYYY-MM-DD)
        period_end: Date de fin (YYYY-MM-DD)
        semester: Semestre (1 ou 2)
        year: Année
    """
    try:
        # Si semestre et année fournis, calculer les dates
        if semester and year:
            semester = int(semester)
            year = int(year)
            
            if semester == 1:
                period_start = f"{year}-01-01"
                period_end = f"{year}-06-30"
            else:
                period_start = f"{year}-07-01"
                period_end = f"{year}-12-31"
        
        # Valeurs par défaut si pas de paramètres
        if not period_start or not period_end:
            current_date = getdate(today())
            current_year = current_date.year
            
            # Déterminer le semestre actuel
            if current_date.month <= 6:
                period_start = f"{current_year}-01-01"
                period_end = f"{current_year}-06-30"
                semester = 1
            else:
                period_start = f"{current_year}-07-01"
                period_end = f"{current_year}-12-31"
                semester = 2
        
        # Générer le fichier Excel
        excel_data = generate_liste_clients(period_start, period_end)
        
        # Nom du fichier basé sur les dates
        start_date = datetime.strptime(period_start, '%Y-%m-%d')
        end_date = datetime.strptime(period_end, '%Y-%m-%d')
        
        semester_names = {
            1: "Janvier à Juin",
            2: "Juillet à Décembre"
        }
        
        if not semester:
            semester = 1 if start_date.month <= 6 else 2
            
        semester_text = semester_names[semester]
        
        filename = f"TIPAccEne - Liste Semestrielle des Clients - Douane - {start_date.year} {semester_text}.xlsx"
        
        # Retourner le fichier pour téléchargement
        frappe.response.update({
            "type": "download",
            "filecontent": excel_data,
            "filename": filename
        })
        
    except Exception as e:
        frappe.throw(_("Erreur lors de la génération de la liste des clients: {0}").format(str(e)))


@frappe.whitelist()
def get_available_periods():
    """
    Récupérer les périodes disponibles pour les déclarations
    """
    try:
        # Récupérer les dates min/max des mouvements GNR
        date_range = frappe.db.sql("""
            SELECT MIN(date) as min_date, MAX(date) as max_date
            FROM `tabMouvement GNR`
            WHERE docstatus = 1
        """, as_dict=True)[0]
        
        periods = {
            "quarters": [],
            "semesters": []
        }
        
        if date_range.min_date and date_range.max_date:
            min_date = getdate(date_range.min_date)
            max_date = getdate(date_range.max_date)
            
            # Générer les trimestres disponibles
            current_year = min_date.year
            end_year = max_date.year
            
            while current_year <= end_year:
                for quarter in range(1, 5):
                    if quarter == 1:
                        q_start = f"{current_year}-01-01"
                        q_end = f"{current_year}-03-31"
                        q_label = f"Q1 {current_year} (Janvier - Mars)"
                    elif quarter == 2:
                        q_start = f"{current_year}-04-01"
                        q_end = f"{current_year}-06-30"
                        q_label = f"Q2 {current_year} (Avril - Juin)"
                    elif quarter == 3:
                        q_start = f"{current_year}-07-01"
                        q_end = f"{current_year}-09-30"
                        q_label = f"Q3 {current_year} (Juillet - Septembre)"
                    else:
                        q_start = f"{current_year}-10-01"
                        q_end = f"{current_year}-12-31"
                        q_label = f"Q4 {current_year} (Octobre - Décembre)"
                    
                    # Vérifier si le trimestre a des données
                    has_data = frappe.db.sql("""
                        SELECT COUNT(*) as count
                        FROM `tabMouvement GNR`
                        WHERE date BETWEEN %s AND %s
                        AND docstatus = 1
                    """, (q_start, q_end))[0][0]
                    
                    if has_data > 0:
                        periods["quarters"].append({
                            "quarter": quarter,
                            "year": current_year,
                            "start_date": q_start,
                            "end_date": q_end,
                            "label": q_label,
                            "count": has_data
                        })
                
                # Générer les semestres disponibles
                for semester in range(1, 3):
                    if semester == 1:
                        s_start = f"{current_year}-01-01"
                        s_end = f"{current_year}-06-30"
                        s_label = f"S1 {current_year} (Janvier - Juin)"
                    else:
                        s_start = f"{current_year}-07-01"
                        s_end = f"{current_year}-12-31"
                        s_label = f"S2 {current_year} (Juillet - Décembre)"
                    
                    # Vérifier si le semestre a des données
                    has_data = frappe.db.sql("""
                        SELECT COUNT(*) as count
                        FROM `tabMouvement GNR`
                        WHERE date BETWEEN %s AND %s
                        AND docstatus = 1
                        AND purpose = 'Material Issue'
                    """, (s_start, s_end))[0][0]
                    
                    if has_data > 0:
                        periods["semesters"].append({
                            "semester": semester,
                            "year": current_year,
                            "start_date": s_start,
                            "end_date": s_end,
                            "label": s_label,
                            "count": has_data
                        })
                
                current_year += 1
        
        return periods
        
    except Exception as e:
        frappe.throw(_("Erreur lors de la récupération des périodes: {0}").format(str(e)))


@frappe.whitelist()
def preview_declaration_data(declaration_type, period_start, period_end):
    """
    Prévisualiser les données qui seront incluses dans la déclaration
    
    Args:
        declaration_type: "arrete_trimestriel" ou "liste_clients"
        period_start: Date de début
        period_end: Date de fin
    """
    try:
        if declaration_type == "arrete_trimestriel":
            # Prévisualiser les données de l'arrêté trimestriel
            movements = frappe.db.sql("""
                SELECT 
                    date,
                    SUM(CASE WHEN purpose = 'Receipt' THEN qty_in_liters ELSE 0 END) as entrees,
                    SUM(CASE WHEN purpose = 'Material Issue' AND customer_category = 'Agricole' 
                        THEN qty_in_liters ELSE 0 END) as sorties_agricole,
                    SUM(CASE WHEN purpose = 'Material Issue' AND (customer_category != 'Agricole' OR customer_category IS NULL) 
                        THEN qty_in_liters ELSE 0 END) as sorties_sans_attestation,
                    COUNT(*) as nb_operations
                FROM `tabMouvement GNR`
                WHERE date BETWEEN %s AND %s
                AND docstatus = 1
                GROUP BY date
                ORDER BY date
            """, (period_start, period_end), as_dict=True)
            
            total_entrees = sum(m.entrees for m in movements)
            total_sorties_agricole = sum(m.sorties_agricole for m in movements)
            total_sorties_sans_attestation = sum(m.sorties_sans_attestation for m in movements)
            
            return {
                "type": "arrete_trimestriel",
                "period_start": period_start,
                "period_end": period_end,
                "movements": movements[:10],  # Premières 10 lignes pour prévisualisation
                "total_movements": len(movements),
                "summary": {
                    "total_entrees": total_entrees,
                    "total_sorties_agricole": total_sorties_agricole,
                    "total_sorties_sans_attestation": total_sorties_sans_attestation,
                    "stock_variation": total_entrees - total_sorties_agricole - total_sorties_sans_attestation
                }
            }
            
        elif declaration_type == "liste_clients":
            # Prévisualiser les données de la liste clients
            clients = frappe.db.sql("""
                SELECT 
                    c.customer_name as raison_sociale,
                    c.tax_id as siren,
                    SUM(m.qty_in_liters / 100) as volume_hl,
                    CASE 
                        WHEN m.customer_category = 'Agricole' THEN 3.86
                        ELSE 24.81 
                    END as tarif_accise,
                    COUNT(*) as nb_livraisons
                FROM `tabMouvement GNR` m
                JOIN `tabCustomer` c ON m.customer = c.name
                WHERE m.date BETWEEN %s AND %s
                AND m.purpose = 'Material Issue'
                AND m.docstatus = 1
                GROUP BY c.name, m.customer_category
                ORDER BY c.customer_name
            """, (period_start, period_end), as_dict=True)
            
            total_volume = sum(c.volume_hl for c in clients)
            nb_clients_agricole = len([c for c in clients if c.tarif_accise == 3.86])
            nb_clients_autres = len([c for c in clients if c.tarif_accise == 24.81])
            
            return {
                "type": "liste_clients",
                "period_start": period_start,
                "period_end": period_end,
                "clients": clients[:20],  # Premiers 20 clients pour prévisualisation
                "total_clients": len(clients),
                "summary": {
                    "total_volume_hl": total_volume,
                    "nb_clients_agricole": nb_clients_agricole,
                    "nb_clients_autres": nb_clients_autres,
                    "total_clients": len(clients)
                }
            }
        
        else:
            frappe.throw(_("Type de déclaration non reconnu"))
            
    except Exception as e:
        frappe.throw(_("Erreur lors de la prévisualisation: {0}").format(str(e)))
@frappe.whitelist()
def test_attestation_system(customer_code=None):
    """
    API de test pour vérifier le fonctionnement du système d'attestation
    
    Args:
        customer_code: Code client à tester (optionnel)
    """
    try:
        results = {
            "success": True,
            "tests": []
        }
        
        # Test 1: Vérifier les champs d'attestation
        if customer_code:
            customers_to_test = [customer_code]
        else:
            # Prendre les 5 premiers clients
            customers_to_test = [c.name for c in frappe.get_all("Customer", limit=5)]
        
        for customer in customers_to_test:
            customer_data = frappe.db.get_value(
                "Customer", 
                customer, 
                ["customer_name", "custom_n_dossier_", "custom_date_de_depot"], 
                as_dict=True
            )
            
            if customer_data:
                # Test de la logique d'attestation
                has_numero = customer_data.get('custom_n_dossier_') and str(customer_data.get('custom_n_dossier_', '')).strip()
                has_date = customer_data.get('custom_date_de_depot')
                has_complete_attestation = bool(has_numero and has_date)
                
                expected_category = "Agricole" if has_complete_attestation else "Autre"
                expected_rate = 3.86 if has_complete_attestation else 24.81
                
                test_result = {
                    "customer_code": customer,
                    "customer_name": customer_data.get('customer_name'),
                    "numero_dossier": customer_data.get('custom_n_dossier_'),
                    "date_depot": customer_data.get('custom_date_de_depot'),
                    "has_complete_attestation": has_complete_attestation,
                    "expected_category": expected_category,
                    "expected_rate": expected_rate,
                    "status": "✅ Attestation détectée correctement" if has_complete_attestation else "⚠️ Pas d'attestation complète"
                }
                
                results["tests"].append(test_result)
        
        return results
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
