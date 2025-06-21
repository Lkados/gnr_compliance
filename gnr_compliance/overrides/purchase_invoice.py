# ==========================================
# FICHIER: gnr_compliance/overrides/purchase_invoice.py
# OVERRIDE pour permettre annulation en cascade des mouvements GNR
# ==========================================

import frappe
from frappe import _
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice


class PurchaseInvoiceGNR(PurchaseInvoice):
    """
    Extension de Purchase Invoice pour gérer l'annulation automatique des mouvements GNR
    """
    
    def before_cancel(self):
        """
        Annule automatiquement les mouvements GNR AVANT la vérification des liens
        """
        try:
            # Annuler d'abord les mouvements GNR liés
            self.cancel_related_gnr_movements()
            
            # Appeler la méthode parent
            super().before_cancel()
            
        except Exception as e:
            frappe.throw(f"Erreur lors de l'annulation des mouvements GNR: {str(e)}")
    
    def cancel_related_gnr_movements(self):
        """
        Annule tous les mouvements GNR liés à cette facture d'achat
        """
        movements = frappe.get_all("Mouvement GNR",
                                  filters={
                                      "reference_document": "Purchase Invoice",
                                      "reference_name": self.name,
                                      "docstatus": 1  # Seulement les soumis
                                  })
        
        movements_cancelled = 0
        for movement in movements:
            try:
                mov_doc = frappe.get_doc("Mouvement GNR", movement.name)
                mov_doc.cancel()
                movements_cancelled += 1
                
            except Exception as e:
                frappe.log_error(f"Erreur annulation mouvement GNR achat {movement.name}: {str(e)}")
                frappe.throw(f"Impossible d'annuler le mouvement GNR {movement.name}")
        
        if movements_cancelled > 0:
            frappe.msgprint(
                f"🔄 {movements_cancelled} mouvement(s) GNR achat annulé(s) automatiquement",
                title="GNR Compliance",
                indicator="orange"
            )
    
    def on_cancel(self):
        """
        Nettoyage après annulation
        """
        try:
            # Appeler la méthode parent
            super().on_cancel()
            
            # Nettoyer les mouvements brouillons restants
            self.cleanup_draft_gnr_movements()
            
        except Exception as e:
            frappe.log_error(f"Erreur nettoyage après annulation facture achat {self.name}: {str(e)}")
    
    def cleanup_draft_gnr_movements(self):
        """
        Supprime les mouvements GNR en brouillon restants
        """
        draft_movements = frappe.get_all("Mouvement GNR",
                                        filters={
                                            "reference_document": "Purchase Invoice",
                                            "reference_name": self.name,
                                            "docstatus": 0  # Brouillons seulement
                                        })
        
        for movement in draft_movements:
            frappe.delete_doc("Mouvement GNR", movement.name, force=1)