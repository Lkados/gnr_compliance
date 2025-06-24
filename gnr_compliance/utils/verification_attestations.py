# gnr_compliance/utils/verification_attestations.py
# Utilitaires pour vérifier les attestations basées sur les champs existants

import frappe
from frappe.utils import format_date, getdate

@frappe.whitelist()
def verifier_attestations_clients():
    """
    Vérifie quels clients ont des attestations basées sur custom_n_dossier_ et custom_date_de_depot
    """
    try:
        # Récupérer tous les clients avec leurs champs d'attestation
        clients = frappe.db.sql("""
            SELECT 
                name,
                customer_name,
                custom_n_dossier_,
                custom_date_de_depot,
                CASE 
                    WHEN custom_n_dossier_ IS NOT NULL AND custom_n_dossier_ != '' AND custom_date_de_depot IS NOT NULL 
                    THEN 1 
                    ELSE 0 
                END as a_attestation
            FROM `tabCustomer`
            ORDER BY customer_name
        """, as_dict=True)
        
        clients_avec_attestation = []
        clients_sans_attestation = []
        clients_incomplets = []
        
        for client in clients:
            if client.a_attestation == 1:
                clients_avec_attestation.append({
                    'code': client.name,
                    'nom': client.customer_name,
                    'numero_dossier': client.custom_n_dossier_,
                    'date_depot': format_date(client.custom_date_de_depot) if client.custom_date_de_depot else ''
                })
            else:
                # Vérifier si c'est incomplet (un seul champ rempli)
                has_numero = client.custom_n_dossier_ and client.custom_n_dossier_.strip()
                has_date = client.custom_date_de_depot
                
                if has_numero and not has_date:
                    clients_incomplets.append({
                        'code': client.name,
                        'nom': client.customer_name,
                        'numero_dossier': client.custom_n_dossier_,
                        'date_depot': 'MANQUANTE',
                        'probleme': 'Date de dépôt manquante'
                    })
                elif has_date and not has_numero:
                    clients_incomplets.append({
                        'code': client.name,
                        'nom': client.customer_name,
                        'numero_dossier': 'MANQUANT',
                        'date_depot': format_date(client.custom_date_de_depot),
                        'probleme': 'Numéro de dossier manquant'
                    })
                else:
                    clients_sans_attestation.append({
                        'code': client.name,
                        'nom': client.customer_name
                    })
        
        return {
            "success": True,
            "total_clients": len(clients),
            "avec_attestation": len(clients_avec_attestation),
            "sans_attestation": len(clients_sans_attestation),
            "incomplets": len(clients_incomplets),
            "details": {
                "clients_avec_attestation": clients_avec_attestation,
                "clients_sans_attestation": clients_sans_attestation,
                "clients_incomplets": clients_incomplets
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur vérification attestations: {str(e)}")
        return {"success": False, "message": f"Erreur: {str(e)}"}

@frappe.whitelist()
def corriger_attestation_client(client_code, numero_dossier=None, date_depot=None):
    """
    Corrige les champs d'attestation pour un client spécifique
    """
    try:
        client_doc = frappe.get_doc("Customer", client_code)
        
        if numero_dossier:
            client_doc.custom_n_dossier_ = numero_dossier
        
        if date_depot:
            client_doc.custom_date_de_depot = getdate(date_depot)
        
        client_doc.save()
        
        return {
            "success": True,
            "message": f"Attestation mise à jour pour {client_doc.customer_name}"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur correction attestation client {client_code}: {str(e)}")
        return {"success": False, "message": f"Erreur: {str(e)}"}

@frappe.whitelist()
def rapport_attestations_periode(from_date, to_date):
    """
    Génère un rapport des attestations pour une période donnée
    """
    try:
        # Récupérer les ventes GNR avec détail des attestations
        ventes = frappe.db.sql("""
            SELECT 
                m.client,
                c.customer_name,
                c.custom_n_dossier_,
                c.custom_date_de_depot,
                SUM(m.quantite) as quantite_totale,
                CASE 
                    WHEN c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL 
                    THEN 'Avec attestation (3,86€/hL)' 
                    ELSE 'Sans attestation (24,81€/hL)' 
                END as statut_attestation,
                CASE 
                    WHEN c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL 
                    THEN SUM(m.quantite) * 3.86 / 100
                    ELSE SUM(m.quantite) * 24.81 / 100
                END as taxe_gnr
            FROM `tabMouvement GNR` m
            LEFT JOIN `tabCustomer` c ON m.client = c.name
            WHERE m.date_mouvement BETWEEN %s AND %s
            AND m.docstatus = 1
            AND m.type_mouvement = 'Vente'
            AND m.client IS NOT NULL
            GROUP BY m.client, c.customer_name, c.custom_n_dossier_, c.custom_date_de_depot
            ORDER BY c.customer_name
        """, (from_date, to_date), as_dict=True)
        
        # Calculer les totaux
        total_avec_attestation = sum([v.quantite_totale for v in ventes if 'Avec attestation' in v.statut_attestation])
        total_sans_attestation = sum([v.quantite_totale for v in ventes if 'Sans attestation' in v.statut_attestation])
        taxe_avec_attestation = sum([v.taxe_gnr for v in ventes if 'Avec attestation' in v.statut_attestation])
        taxe_sans_attestation = sum([v.taxe_gnr for v in ventes if 'Sans attestation' in v.statut_attestation])
        
        return {
            "success": True,
            "periode": f"{from_date} au {to_date}",
            "resume": {
                "total_avec_attestation": round(total_avec_attestation, 2),
                "total_sans_attestation": round(total_sans_attestation, 2),
                "taxe_avec_attestation": round(taxe_avec_attestation, 2),
                "taxe_sans_attestation": round(taxe_sans_attestation, 2),
                "nb_clients_avec": len([v for v in ventes if 'Avec attestation' in v.statut_attestation]),
                "nb_clients_sans": len([v for v in ventes if 'Sans attestation' in v.statut_attestation])
            },
            "details": ventes
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur rapport attestations: {str(e)}")
        return {"success": False, "message": f"Erreur: {str(e)}"}