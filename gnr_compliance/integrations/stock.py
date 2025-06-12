# gnr_compliance/integrations/stock.py
import frappe

def capture_mouvement_stock(doc, method):
    """Capture des mouvements de stock pour produits GNR"""
    if doc.stock_entry_type in ["Material Receipt", "Material Issue", "Material Transfer"]:
        for item in doc.items:
            is_gnr = frappe.get_value("Item", item.item_code, "custom_gnr_applicable")
            if is_gnr:
                type_mouvement = {
                    "Material Receipt": "Entrée",
                    "Material Issue": "Sortie",
                    "Material Transfer": "Transfert"
                }.get(doc.stock_entry_type)
                
                mouvement_gnr = frappe.get_doc({
                    "doctype": "Mouvement GNR",
                    "type_mouvement": type_mouvement,
                    "date_mouvement": doc.posting_date,
                    "reference_document": doc.doctype,
                    "reference_name": doc.name,
                    "code_produit": item.item_code,
                    "quantite": item.qty,
                    "entrepot_source": item.s_warehouse,
                    "entrepot_destination": item.t_warehouse
                })
                mouvement_gnr.insert()
                mouvement_gnr.submit()