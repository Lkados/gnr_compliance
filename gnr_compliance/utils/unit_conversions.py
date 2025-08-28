# gnr_compliance/utils/unit_conversions.py
import frappe
from frappe.utils import flt

# Définition des conversions vers LITRES (unité de base)
UNIT_CONVERSIONS = {
    # Unités de volume
    "L": 1,            # Litre
    "l": 1,            # litre
    "Litre": 1,
    "Litres": 1,
    "hL": 100,         # Hectolitre = 100 litres
    "hl": 100,
    "Hectolitre": 100,
    "Hectolitres": 100,
    "m³": 1000,        # Mètre cube = 1000 litres
    "m3": 1000,
    "M3": 1000,
    "Mètre Cube": 1000,
    "Mètres Cubes": 1000,
    "Cubic Meter": 1000,
    "CBM": 1000,
    
    # Unités spécifiques carburants (si utilisées)
    "Gallon": 3.78541,  # Gallon US
    "Barrel": 158.987,  # Baril de pétrole
}

def convert_to_litres(quantity, from_unit):
    """
    Convertit une quantité en litres
    
    Args:
        quantity: Quantité à convertir
        from_unit: Unité source (m³, hL, L, etc.)
    
    Returns:
        float: Quantité en litres
    """
    if not from_unit:
        # Si pas d'unité, on assume que c'est déjà en litres
        return flt(quantity)
    
    # Nettoyer l'unité (enlever espaces, etc.)
    from_unit = from_unit.strip()
    
    # Chercher le facteur de conversion
    conversion_factor = UNIT_CONVERSIONS.get(from_unit)
    
    if not conversion_factor:
        # Essayer avec une recherche insensible à la casse
        for unit, factor in UNIT_CONVERSIONS.items():
            if unit.lower() == from_unit.lower():
                conversion_factor = factor
                break
    
    if conversion_factor:
        return flt(quantity) * conversion_factor
    else:
        # Si unité non trouvée, logger et retourner la quantité telle quelle
        frappe.logger().warning(f"[GNR] Unité non reconnue: {from_unit}. Pas de conversion appliquée.")
        return flt(quantity)

def convert_to_hectolitres(quantity, from_unit):
    """
    Convertit une quantité en hectolitres
    
    Args:
        quantity: Quantité à convertir
        from_unit: Unité source
    
    Returns:
        float: Quantité en hectolitres
    """
    litres = convert_to_litres(quantity, from_unit)
    return litres / 100

def convert_from_litres(quantity_litres, to_unit):
    """
    Convertit des litres vers une autre unité
    
    Args:
        quantity_litres: Quantité en litres
        to_unit: Unité cible
    
    Returns:
        float: Quantité dans l'unité cible
    """
    to_unit = to_unit.strip()
    
    # Chercher le facteur de conversion
    conversion_factor = UNIT_CONVERSIONS.get(to_unit)
    
    if not conversion_factor:
        # Essayer avec une recherche insensible à la casse
        for unit, factor in UNIT_CONVERSIONS.items():
            if unit.lower() == to_unit.lower():
                conversion_factor = factor
                break
    
    if conversion_factor:
        return flt(quantity_litres) / conversion_factor
    else:
        return flt(quantity_litres)

@frappe.whitelist()
def get_item_unit(item_code):
    """
    Récupère l'unité de mesure d'un article
    """
    return frappe.get_value("Item", item_code, "stock_uom") or "L"

