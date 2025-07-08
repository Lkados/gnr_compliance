import frappe
from frappe.utils import getdate, add_years, add_months
from datetime import datetime

def client_a_attestation_valide(client_code):
    """
    Fonction simple pour vérifier si un client a une attestation valide
    Retourne True si valide, False sinon
    """
    try:
        client = frappe.get_doc("Customer", client_code)
        
        # Vérifier que les deux champs sont remplis
        if not client.custom_n_dossier_ or not client.custom_date_de_depot:
            return False
        
        # Vérifier que l'attestation n'est pas expirée
        date_depot = getdate(client.custom_date_de_depot)
        date_expiration = add_years(date_depot, 3)  # +3 ans
        aujourd_hui = getdate()
        
        return aujourd_hui <= date_expiration
        
    except:
        return False

def get_message_statut_attestation(client_code):
    """
    Retourne le message de statut d'une attestation
    """
    try:
        client = frappe.get_doc("Customer", client_code)
        
        if not client.custom_n_dossier_ or not client.custom_date_de_depot:
            return "Sans attestation"
        
        date_depot = getdate(client.custom_date_de_depot)
        date_expiration = add_years(date_depot, 3)
        date_alerte = add_months(date_expiration, -3)
        aujourd_hui = getdate()
        
        if aujourd_hui > date_expiration:
            return "Attestation périmée"
        elif aujourd_hui > date_alerte:
            jours = (date_expiration - aujourd_hui).days
            return f"Attestation bientôt expirer ({jours} jours)"
        else:
            return "Tarif d'accise réduit sur le GNR"
            
    except:
        return "Erreur vérification"

def get_taux_selon_attestation(client_code):
    """
    Retourne le taux GNR à appliquer selon le statut de l'attestation
    3.86 si valide, 24.81 sinon
    """
    if client_a_attestation_valide(client_code):
        return 3.86  # Tarif réduit
    else:
        return 24.81  # Tarif normal

@frappe.whitelist()
def mise_a_jour_sql_attestations():
    """
    Met à jour directement en SQL pour optimiser les requêtes
    Ajoute une condition d'expiration dans les calculs existants
    """
    # Cette condition SQL peut être utilisée dans les requêtes
    condition_attestation_valide = """
    (c.custom_n_dossier_ IS NOT NULL 
     AND c.custom_n_dossier_ != '' 
     AND c.custom_date_de_depot IS NOT NULL 
     AND DATE_ADD(c.custom_date_de_depot, INTERVAL 3 YEAR) > CURDATE())
    """
    
    return condition_attestation_valide

# Fonction pour les exports - remplace la logique existante
def calculer_volumes_avec_attestation_valide(from_date, to_date):
    """
    Calcule les volumes avec attestation VALIDE (non expirée) pour une période
    """
    try:
        result = frappe.db.sql("""
            SELECT 
                SUM(CASE 
                    WHEN m.type_mouvement = 'Vente' 
                    AND c.custom_n_dossier_ IS NOT NULL 
                    AND c.custom_n_dossier_ != '' 
                    AND c.custom_date_de_depot IS NOT NULL 
                    AND DATE_ADD(c.custom_date_de_depot, INTERVAL 3 YEAR) > CURDATE()
                    THEN m.quantite 
                    ELSE 0 
                END) as volume_avec_attestation_valide,
                SUM(CASE 
                    WHEN m.type_mouvement = 'Vente' 
                    AND (c.custom_n_dossier_ IS NULL 
                         OR c.custom_n_dossier_ = '' 
                         OR c.custom_date_de_depot IS NULL 
                         OR DATE_ADD(c.custom_date_de_depot, INTERVAL 3 YEAR) <= CURDATE())
                    THEN m.quantite 
                    ELSE 0 
                END) as volume_sans_attestation_ou_expiree
            FROM `tabMouvement GNR` m
            LEFT JOIN `tabCustomer` c ON m.client = c.name
            WHERE m.date_mouvement BETWEEN %s AND %s
            AND m.docstatus = 1
        """, (from_date, to_date), as_dict=True)
        
        if result:
            return result[0]
        else:
            return {
                "volume_avec_attestation_valide": 0,
                "volume_sans_attestation_ou_expiree": 0
            }
            
    except Exception as e:
        frappe.log_error(f"Erreur calcul volumes attestation valide: {str(e)}")
        return {
            "volume_avec_attestation_valide": 0,
            "volume_sans_attestation_ou_expiree": 0
        }

# Pour remplacer dans les fichiers existants
def get_condition_sql_attestation_valide():
    """
    Retourne la condition SQL pour attestation valide (non expirée)
    À utiliser dans toutes les requêtes existantes
    """
    return """
    (c.custom_n_dossier_ IS NOT NULL 
     AND c.custom_n_dossier_ != '' 
     AND c.custom_date_de_depot IS NOT NULL 
     AND DATE_ADD(c.custom_date_de_depot, INTERVAL 3 YEAR) > CURDATE())
    """