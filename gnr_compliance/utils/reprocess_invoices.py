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
        query = f"""
            SELECT DISTINCT 
                si.name,
                si.posting_date,
                si.customer,
                COUNT(DISTINCT sii.item_code) as nb_items_gnr,
                SUM(sii.qty) as total_qty
            FROM `tabSales Invoice` si
            INNER JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
            INNER JOIN `tabItem` i ON sii.item_code = i.name
            WHERE {where_clause}
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
        """
        
        invoices = frappe.db.sql(query, values, as_dict=True)
        
        frappe.logger().info(f"[GNR] Trouvé {len(invoices)} factures de vente à retraiter")
        
        processed = 0
        errors = []
        
        for invoice in invoices:
            try:
                frappe.logger().info(f"[GNR] Traitement facture {invoice.name} avec {invoice.nb_items_gnr} articles GNR")
                
                from gnr_compliance.integrations.sales import capture_vente_gnr
                doc = frappe.get_doc("Sales Invoice", invoice.name)
                capture_vente_gnr(doc, "reprocess")
                processed += 1
                
            except Exception as e:
                error_msg = f"{invoice.name}: {str(e)}"
                frappe.logger().error(f"[GNR] Erreur: {error_msg}")
                errors.append(error_msg)
        
        return {
            'success': True,
            'message': f"{processed} factures retraitées sur {len(invoices)} trouvées",
            'processed': processed,
            'found': len(invoices),
            'errors': errors if errors else None
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur retraitement factures: {str(e)}")
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
        query = f"""
            SELECT DISTINCT 
                pi.name,
                pi.posting_date,
                pi.supplier,
                COUNT(DISTINCT pii.item_code) as nb_items_gnr,
                SUM(pii.qty) as total_qty
            FROM `tabPurchase Invoice` pi
            INNER JOIN `tabPurchase Invoice Item` pii ON pi.name = pii.parent
            INNER JOIN `tabItem` i ON pii.item_code = i.name
            WHERE {where_clause}
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
        """
        
        invoices = frappe.db.sql(query, values, as_dict=True)
        
        frappe.logger().info(f"[GNR] Trouvé {len(invoices)} factures d'achat à retraiter")
        
        processed = 0
        errors = []
        
        for invoice in invoices:
            try:
                frappe.logger().info(f"[GNR] Traitement facture achat {invoice.name}")
                
                from gnr_compliance.integrations.sales import capture_achat_gnr
                doc = frappe.get_doc("Purchase Invoice", invoice.name)
                capture_achat_gnr(doc, "reprocess")
                processed += 1
                
            except Exception as e:
                error_msg = f"{invoice.name}: {str(e)}"
                frappe.logger().error(f"[GNR] Erreur: {error_msg}")
                errors.append(error_msg)
        
        return {
            'success': True,
            'message': f"{processed} factures d'achat retraitées sur {len(invoices)} trouvées",
            'processed': processed,
            'found': len(invoices),
            'errors': errors if errors else None
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur retraitement factures achat: {str(e)}")
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
        stats = frappe.db.sql(f"""
            SELECT 
                COUNT(DISTINCT inv.name) as total_invoices,
                COUNT(DISTINCT CASE WHEN i.is_gnr_tracked = 1 THEN inv.name END) as invoices_with_gnr,
                COUNT(DISTINCT m.reference_name) as invoices_processed,
                SUM(CASE WHEN i.is_gnr_tracked = 1 THEN inv_item.qty ELSE 0 END) as total_gnr_qty,
                COUNT(DISTINCT CASE WHEN i.is_gnr_tracked = 1 THEN i.name END) as unique_gnr_items
            FROM `tab{table}` inv
            LEFT JOIN `tab{item_table}` inv_item ON inv.name = inv_item.parent
            LEFT JOIN `tabItem` i ON inv_item.item_code = i.name
            LEFT JOIN `tabMouvement GNR` m ON m.reference_document = '{table}' 
                AND m.reference_name = inv.name AND m.docstatus = 1
            WHERE {where_clause}
        """, values, as_dict=True)
        
        print(f"\n📊 Statistiques factures {invoice_type} GNR:")
        print(f"  Période: {from_date or 'Début'} au {to_date or 'Aujourd\'hui'}")
        if stats:
            s = stats[0]
            print(f"  Total factures: {s.total_invoices}")
            print(f"  Factures avec articles GNR: {s.invoices_with_gnr}")
            print(f"  Factures traitées GNR: {s.invoices_processed}")
            print(f"  Factures à traiter: {s.invoices_with_gnr - s.invoices_processed}")
            print(f"  Quantité totale GNR: {s.total_gnr_qty or 0}")
            print(f"  Articles GNR uniques: {s.unique_gnr_items}")
        
        # Liste des factures non traitées
        if stats and s.invoices_with_gnr > s.invoices_processed:
            print(f"\n📋 Factures avec GNR non traité (max 10):")
            
            unprocessed = frappe.db.sql(f"""
                SELECT DISTINCT 
                    inv.name,
                    inv.posting_date,
                    inv.{party_field} as party,
                    GROUP_CONCAT(DISTINCT i.name) as gnr_items
                FROM `tab{table}` inv
                INNER JOIN `tab{item_table}` inv_item ON inv.name = inv_item.parent
                INNER JOIN `tabItem` i ON inv_item.item_code = i.name
                WHERE {where_clause}
                AND i.is_gnr_tracked = 1
                AND NOT EXISTS (
                    SELECT 1 FROM `tabMouvement GNR` m 
                    WHERE m.reference_document = '{table}' 
                    AND m.reference_name = inv.name
                    AND m.docstatus = 1
                )
                GROUP BY inv.name
                ORDER BY inv.posting_date DESC
                LIMIT 10
            """, values, as_dict=True)
            
            for inv in unprocessed:
                print(f"  - {inv.name} ({inv.posting_date}) - {inv.party} - Articles: {inv.gnr_items}")
        
        return stats[0] if stats else {}
        
    except Exception as e:
        frappe.log_error(f"Erreur check status factures: {str(e)}")
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
        conditions = ["docstatus = 1"]
        values = [item_code]
        
        if from_date:
            conditions.append("posting_date >= %s")
            values.append(from_date)
        
        if to_date:
            conditions.append("posting_date <= %s")
            values.append(to_date)
        
        where_clause = " AND ".join(conditions)
        
        # Rechercher dans Sales Invoice
        sales_invoices = frappe.db.sql(f"""
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
            AND si.{where_clause}
            ORDER BY si.posting_date DESC
            LIMIT 20
        """, values, as_dict=True)
        
        # Rechercher dans Purchase Invoice
        purchase_invoices = frappe.db.sql(f"""
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
            AND pi.{where_clause}
            ORDER BY pi.posting_date DESC
            LIMIT 20
        """, values, as_dict=True)
        
        print(f"\n🔍 Factures contenant l'article {item_code}:")
        
        if sales_invoices:
            print(f"\n  📤 Factures de vente ({len(sales_invoices)}):")
            for inv in sales_invoices[:5]:
                status = "✅ Traité" if inv.has_gnr_movement else "❌ Non traité"
                print(f"    - {inv.name} ({inv.posting_date}) - {inv.party} - Qty: {inv.qty} - {status}")
        
        if purchase_invoices:
            print(f"\n  📥 Factures d'achat ({len(purchase_invoices)}):")
            for inv in purchase_invoices[:5]:
                status = "✅ Traité" if inv.has_gnr_movement else "❌ Non traité"
                print(f"    - {inv.name} ({inv.posting_date}) - {inv.party} - Qty: {inv.qty} - {status}")
        
        return {
            'sales_invoices': sales_invoices,
            'purchase_invoices': purchase_invoices,
            'total_found': len(sales_invoices) + len(purchase_invoices)
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur recherche factures avec article {item_code}: {str(e)}")
        return {'error': str(e)}

@frappe.whitelist()
def test_invoice_capture(invoice_type, invoice_name):
    """
    Teste la capture GNR sur une facture spécifique
    
    Args:
        invoice_type: "Sales Invoice" ou "Purchase Invoice"
        invoice_name: Nom de la facture
    """
    try:
        doc = frappe.get_doc(invoice_type, invoice_name)
        
        print(f"\n🧪 Test capture GNR pour {invoice_type} {invoice_name}")
        print(f"  Date: {doc.posting_date}")
        print(f"  Statut: {'Soumis' if doc.docstatus == 1 else 'Brouillon'}")
        
        if invoice_type == "Sales Invoice":
            print(f"  Client: {doc.customer}")
            from gnr_compliance.integrations.sales import capture_vente_gnr
            capture_vente_gnr(doc, "test")
        else:
            print(f"  Fournisseur: {doc.supplier}")
            from gnr_compliance.integrations.sales import capture_achat_gnr
            capture_achat_gnr(doc, "test")
        
        return {'success': True, 'message': 'Test exécuté - vérifiez les mouvements GNR'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}