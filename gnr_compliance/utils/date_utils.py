# gnr_compliance/utils/date_utils.py
"""
Utilitaires de dates communes pour GNR Compliance
Centralise toutes les fonctions de calcul de périodes
"""
from frappe.utils import getdate

def get_quarter_from_date(date_obj):
    """Calcule le trimestre à partir d'une date"""
    if isinstance(date_obj, str):
        date_obj = getdate(date_obj)
    return str((date_obj.month - 1) // 3 + 1)

def get_semestre_from_date(date_obj):
    """Calcule le semestre à partir d'une date"""
    if isinstance(date_obj, str):
        date_obj = getdate(date_obj)
    return "1" if date_obj.month <= 6 else "2"

def get_period_dates(periode_type, periode, annee):
    """
    Retourne les dates de début et fin pour une période donnée
    
    Args:
        periode_type (str): "Trimestriel", "Semestriel", "Annuel"
        periode (str): "T1", "T2", "T3", "T4", "S1", "S2", "ANNEE"
        annee (int): Année concernée
        
    Returns:
        tuple: (date_debut, date_fin)
    """
    from datetime import datetime, date
    
    if periode_type == "Trimestriel":
        quarter_dates = {
            "T1": (date(annee, 1, 1), date(annee, 3, 31)),
            "T2": (date(annee, 4, 1), date(annee, 6, 30)),
            "T3": (date(annee, 7, 1), date(annee, 9, 30)),
            "T4": (date(annee, 10, 1), date(annee, 12, 31))
        }
        return quarter_dates.get(periode, (date(annee, 1, 1), date(annee, 12, 31)))
    
    elif periode_type == "Semestriel":
        semester_dates = {
            "S1": (date(annee, 1, 1), date(annee, 6, 30)),
            "S2": (date(annee, 7, 1), date(annee, 12, 31))
        }
        return semester_dates.get(periode, (date(annee, 1, 1), date(annee, 12, 31)))
    
    else:  # Annuel
        return (date(annee, 1, 1), date(annee, 12, 31))