# gnr_compliance/report/analyse_gnr/analyse_gnr.py
import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    summary = get_summary(data)
    
    return columns, data, None, chart, summary

def get_columns():
    return [
        {
            "label": _("Trimestre"),
            "fieldname": "trimestre",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Code Produit"),
            "fieldname": "code_produit",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "label": _("Stock Début"),
            "fieldname": "stock_debut",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Entrées"),
            "fieldname": "entrees",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Sorties"),
            "fieldname": "sorties",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Stock Fin"),
            "fieldname": "stock_fin",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Taxe GNR (€)"),
            "fieldname": "taxe_gnr",
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = []
    values = []
    
    if filters.get("from_date"):
        conditions.append("m.date_mouvement >= %s")
        values.append(filters["from_date"])
    
    if filters.get("to_date"):
        conditions.append("m.date_mouvement <= %s")
        values.append(filters["to_date"])
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    return frappe.db.sql(f"""
        SELECT 
            CONCAT('T', m.trimestre, '-', m.annee) as trimestre,
            m.code_produit,
            COALESCE(stock_debut.quantite, 0) as stock_debut,
            COALESCE(SUM(CASE WHEN m.type_mouvement IN ('Achat', 'Entrée') THEN m.quantite ELSE 0 END), 0) as entrees,
            COALESCE(SUM(CASE WHEN m.type_mouvement IN ('Vente', 'Sortie') THEN m.quantite ELSE 0 END), 0) as sorties,
            COALESCE(stock_fin.quantite, 0) as stock_fin,
            COALESCE(SUM(m.montant_taxe_gnr), 0) as taxe_gnr
        FROM `tabMouvement GNR` m
        LEFT JOIN `tabStock GNR` stock_debut ON stock_debut.code_produit = m.code_produit 
            AND stock_debut.periode = CONCAT(m.trimestre-1, '-', m.annee)
        LEFT JOIN `tabStock GNR` stock_fin ON stock_fin.code_produit = m.code_produit 
            AND stock_fin.periode = CONCAT(m.trimestre, '-', m.annee)
        WHERE m.docstatus = 1 AND {where_clause}
        GROUP BY m.code_produit, m.trimestre, m.annee
        ORDER BY m.annee DESC, m.trimestre DESC, m.code_produit
    """, values, as_dict=True)