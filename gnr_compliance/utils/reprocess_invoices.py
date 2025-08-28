# gnr_compliance/utils/reprocess_invoices.py
import frappe
from frappe.utils import getdate

@frappe.whitelist()
def reprocess_sales_invoices(from_date=None, to_date=None):
    """
    Retraite les factures de vente pour capturer les mouvements GNR manqués
    """
    try:
        conditions = ["si.docstatus = 1"]
        values = []
        
        if from_date:
            conditions.append("si.posting_date >= %s")
            values.append(from_date)
        
        if to_date:
            conditions.append("si.posting_date <= %s")
            values.append(to_date)
        
        where_clause = " AND ".join(conditions)
        
        # Chercher les factures avec articles GNR non traités
        query = """
            SELECT DISTINCT 
                si.name,
                si.posting_date,
                si.customer,
                COUNT(DISTINCT sii.item_code) as nb_items_gnr,
                SUM(sii.qty) as total_qty
            FROM `tabSales Invoice` si
            INNER JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
            INNER JOIN `tabItem` i ON sii.item_code = i.name
            WHERE {}
            AND i.is_gnr_tracked = 1
            AND NOT EXISTS (
                SELECT 1 FROM `tabMouvement GNR` m 
                WHERE m.reference_document = 'Sales Invoice' 
                AND m.reference_name = si.name
                AND m.code_produit = sii.item_code
                AND m.docstatus = 1
            )
            GROUP BY si.name
            ORDER BY si.posting_date DESC
            LIMIT 100
        """.format(where_clause)
        
        invoices = frappe.db.sql(query, values, as_dict=True)
        
        frappe.logger().info("[GNR] Trouvé {} factures de vente à retraiter".format(len(invoices)))
        
        processed = 0
        errors = []
        
        for invoice in invoices:
            try:
                frappe.logger().info("[GNR] Traitement facture {} avec {} articles GNR".format(
                    invoice.name, invoice.nb_items_gnr))
                
                from gnr_compliance.integrations.sales import capture_vente_gnr
                doc = frappe.get_doc("Sales Invoice", invoice.name)
                capture_vente_gnr(doc, "reprocess")
                processed += 1
                
            except Exception as e:
                error_msg = "{}: {}".format(invoice.name, str(e))
                frappe.logger().error("[GNR] Erreur: {}".format(error_msg))
                errors.append(error_msg)
        
        return {
            'success': True,
            'message': "{} factures retraitées sur {} trouvées".format(processed, len(invoices)),
            'processed': processed,
            'found': len(invoices),
            'errors': errors if errors else None
        }
        
    except Exception as e:
        frappe.log_error("Erreur retraitement factures: {}".format(str(e)))
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def reprocess_purchase_invoices(from_date=None, to_date=None):
    """
    Retraite les factures d'achat pour capturer les mouvements GNR manqués
    """
    try:
        conditions = ["pi.docstatus = 1"]
        values = []
        
        if from_date:
            conditions.append("pi.posting_date >= %s")
            values.append(from_date)
        
        if to_date:
            conditions.append("pi.posting_date <= %s")
            values.append(to_date)
        
        where_clause = " AND ".join(conditions)
        
        # Chercher les factures avec articles GNR non traités
        query = """
            SELECT DISTINCT 
                pi.name,
                pi.posting_date,
                pi.supplier,
                COUNT(DISTINCT pii.item_code) as nb_items_gnr,
                SUM(pii.qty) as total_qty
            FROM `tabPurchase Invoice` pi
            INNER JOIN `tabPurchase Invoice Item` pii ON pi.name = pii.parent
            INNER JOIN `tabItem` i ON pii.item_code = i.name
            WHERE {}
            AND i.is_gnr_tracked = 1
            AND NOT EXISTS (
                SELECT 1 FROM `tabMouvement GNR` m 
                WHERE m.reference_document = 'Purchase Invoice' 
                AND m.reference_name = pi.name
                AND m.code_produit = pii.item_code
                AND m.docstatus = 1
            )
            GROUP BY pi.name
            ORDER BY pi.posting_date DESC
            LIMIT 100
        """.format(where_clause)
        
        invoices = frappe.db.sql(query, values, as_dict=True)
        
        frappe.logger().info("[GNR] Trouvé {} factures d'achat à retraiter".format(len(invoices)))
        
        processed = 0
        errors = []
        
        for invoice in invoices:
            try:
                frappe.logger().info("[GNR] Traitement facture achat {}".format(invoice.name))
                
                from gnr_compliance.integrations.sales import capture_achat_gnr
                doc = frappe.get_doc("Purchase Invoice", invoice.name)
                capture_achat_gnr(doc, "reprocess")
                processed += 1
                
            except Exception as e:
                error_msg = "{}: {}".format(invoice.name, str(e))
                frappe.logger().error("[GNR] Erreur: {}".format(error_msg))
                errors.append(error_msg)
        
        return {
            'success': True,
            'message': "{} factures d'achat retraitées sur {} trouvées".format(processed, len(invoices)),
            'processed': processed,
            'found': len(invoices),
            'errors': errors if errors else None
        }
        
    except Exception as e:
        frappe.log_error("Erreur retraitement factures achat: {}".format(str(e)))
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def check_invoice_gnr_status(from_date=None, to_date=None, invoice_type="Sales"):
    """
    Vérifie le statut GNR des factures
    
    Args:
        from_date: Date de début
        to_date: Date de fin
        invoice_type: "Sales" ou "Purchase"
    """
    try:
        if invoice_type == "Sales":
            table = "Sales Invoice"
            item_table = "Sales Invoice Item"
            party_field = "customer"
        else:
            table = "Purchase Invoice"
            item_table = "Purchase Invoice Item"
            party_field = "supplier"
        
        conditions = ["inv.docstatus = 1"]
        values = []
        
        if from_date:
            conditions.append("inv.posting_date >= %s")
            values.append(from_date)
        
        if to_date:
            conditions.append("inv.posting_date <= %s")
            values.append(to_date)
        
        where_clause = " AND ".join(conditions)
        
        # Statistiques globales
        query = """
            SELECT 
                COUNT(DISTINCT inv.name) as total_invoices,
                COUNT(DISTINCT CASE WHEN i.is_gnr_tracked = 1 THEN inv.name END) as invoices_with_gnr,
                COUNT(DISTINCT m.reference_name) as invoices_processed,
                SUM(CASE WHEN i.is_gnr_tracked = 1 THEN inv_item.qty ELSE 0 END) as total_gnr_qty,
                COUNT(DISTINCT CASE WHEN i.is_gnr_tracked = 1 THEN i.name END) as unique_gnr_items
            FROM `tab{}` inv
            LEFT JOIN `tab{}` inv_item ON inv.name = inv_item.parent
            LEFT JOIN `tabItem` i ON inv_item.item_code = i.name
            LEFT JOIN `tabMouvement GNR` m ON m.reference_document = '{}' 
                AND m.reference_name = inv.name AND m.docstatus = 1
            WHERE {}
        """.format(table, item_table, table, where_clause)
        
        stats = frappe.db.sql(query, values, as_dict=True)
        
        print("\n📊 Statistiques factures {} GNR:".format(invoice_type))
        print("  Période: {} au {}".format(from_date or 'Début', to_date or 'Aujourd\'hui'))
        if stats:
            s = stats[0]
            print("  Total factures: {}".format(s.total_invoices))
            print("  Factures avec articles GNR: {}".format(s.invoices_with_gnr))
            print("  Factures traitées GNR: {}".format(s.invoices_processed))
            print("  Factures à traiter: {}".format(s.invoices_with_gnr - s.invoices_processed if s.invoices_with_gnr else 0))
            print("  Quantité totale GNR: {}".format(s.total_gnr_qty or 0))
            print("  Articles GNR uniques: {}".format(s.unique_gnr_items))
        
        # Liste des factures non traitées
        if stats and s.invoices_with_gnr and s.invoices_with_gnr > s.invoices_processed:
            print("\n📋 Factures avec GNR non traité (max 10):")
            
            query_unprocessed = """
                SELECT DISTINCT 
                    inv.name,
                    inv.posting_date,
                    inv.{} as party,
                    GROUP_CONCAT(DISTINCT i.name) as gnr_items
                FROM `tab{}` inv
                INNER JOIN `tab{}` inv_item ON inv.name = inv_item.parent
                INNER JOIN `tabItem` i ON inv_item.item_code = i.name
                WHERE {}
                AND i.is_gnr_tracked = 1
                AND NOT EXISTS (
                    SELECT 1 FROM `tabMouvement GNR` m 
                    WHERE m.reference_document = '{}' 
                    AND m.reference_name = inv.name
                    AND m.docstatus = 1
                )
                GROUP BY inv.name
                ORDER BY inv.posting_date DESC
                LIMIT 10
            """.format(party_field, table, item_table, where_clause, table)
            
            unprocessed = frappe.db.sql(query_unprocessed, values, as_dict=True)
            
            for inv in unprocessed:
                print("  - {} ({}) - {} - Articles: {}".format(
                    inv.name, inv.posting_date, inv.party, inv.gnr_items))
        
        return stats[0] if stats else {}
        
    except Exception as e:
        frappe.log_error("Erreur check status factures: {}".format(str(e)))
        return {'error': str(e)}

@frappe.whitelist()
def find_invoices_with_gnr_item(item_code, from_date=None, to_date=None):
    """
    Trouve toutes les factures contenant un article GNR spécifique
    
    Args:
        item_code: Code de l'article à rechercher
        from_date: Date de début optionnelle
        to_date: Date de fin optionnelle
    """
    try:
        conditions_sales = ["si.docstatus = 1"]
        conditions_purchase = ["pi.docstatus = 1"]
        values_sales = [item_code]
        values_purchase = [item_code]
        
        if from_date:
            conditions_sales.append("si.posting_date >= %s")
            conditions_purchase.append("pi.posting_date >= %s")
            values_sales.append(from_date)
            values_purchase.append(from_date)
        
        if to_date:
            conditions_sales.append("si.posting_date <= %s")
            conditions_purchase.append("pi.posting_date <= %s")
            values_sales.append(to_date)
            values_purchase.append(to_date)
        
        where_sales = " AND ".join(conditions_sales)
        where_purchase = " AND ".join(conditions_purchase)
        
        # Rechercher dans Sales Invoice
        query_sales = """
            SELECT 
                si.name,
                'Sales Invoice' as doctype,
                si.posting_date,
                si.customer as party,
                sii.qty,
                sii.rate,
                sii.amount,
                EXISTS(
                    SELECT 1 FROM `tabMouvement GNR` m 
                    WHERE m.reference_document = 'Sales Invoice' 
                    AND m.reference_name = si.name
                    AND m.code_produit = sii.item_code
                    AND m.docstatus = 1
                ) as has_gnr_movement
            FROM `tabSales Invoice` si
            JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
            WHERE sii.item_code = %s
            AND {}
            ORDER BY si.posting_date DESC
            LIMIT 20
        """.format(where_sales)
        
        sales_invoices = frappe.db.sql(query_sales, values_sales, as_dict=True)
        
        # Rechercher dans Purchase Invoice
        query_purchase = """
            SELECT 
                pi.name,
                'Purchase Invoice' as doctype,
                pi.posting_date,
                pi.supplier as party,
                pii.qty,
                pii.rate,
                pii.amount,
                EXISTS(
                    SELECT 1 FROM `tabMouvement GNR` m 
                    WHERE m.reference_document = 'Purchase Invoice' 
                    AND m.reference_name = pi.name
                    AND m.code_produit = pii.item_code
                    AND m.docstatus = 1
                ) as has_gnr_movement
            FROM `tabPurchase Invoice` pi
            JOIN `tabPurchase Invoice Item` pii ON pi.name = pii.parent
            WHERE pii.item_code = %s
            AND {}
            ORDER BY pi.posting_date DESC
            LIMIT 20
        """.format(where_purchase)
        
        purchase_invoices = frappe.db.sql(query_purchase, values_purchase, as_dict=True)
        
        print("\n🔍 Factures contenant l'article {}:".format(item_code))
        
        if sales_invoices:
            print("\n  📤 Factures de vente ({}):".format(len(sales_invoices)))
            for inv in sales_invoices[:5]:
                status = "✅ Traité" if inv.has_gnr_movement else "❌ Non traité"
                print("    - {} ({}) - {} - Qty: {} - {}".format(
                    inv.name, inv.posting_date, inv.party, inv.qty, status))
        
        if purchase_invoices:
            print("\n  📥 Factures d'achat ({}):".format(len(purchase_invoices)))
            for inv in purchase_invoices[:5]:
                status = "✅ Traité" if inv.has_gnr_movement else "❌ Non traité"
                print("    - {} ({}) - {} - Qty: {} - {}".format(
                    inv.name, inv.posting_date, inv.party, inv.qty, status))
        
        return {
            'sales_invoices': sales_invoices,
            'purchase_invoices': purchase_invoices,
            'total_found': len(sales_invoices) + len(purchase_invoices)
        }
        
    except Exception as e:
        frappe.log_error("Erreur recherche factures avec article {}: {}".format(item_code, str(e)))
        return {'error': str(e)}

