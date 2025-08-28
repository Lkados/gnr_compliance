# ==========================================
# FICHIER: gnr_compliance/utils/gnr_cancel_helper.py
# UTILITAIRE pour annuler factures avec mouvements GNR
# ==========================================

import frappe
from frappe import _

@frappe.whitelist()
def cancel_invoice_with_gnr(doctype, name):
    """
    Annule une facture (Sales ou Purchase) et ses mouvements GNR automatiquement
    
    Args:
        doctype: 'Sales Invoice' ou 'Purchase Invoice'
        name: Nom du document à annuler
    
    Returns:
        dict: Résultat de l'opération
    """
    try:
        # Vérifier les permissions
        if not frappe.has_permission(doctype, "cancel"):
            frappe.throw(_("Permissions insuffisantes pour annuler ce document"))
        
        # 1. Annuler d'abord tous les mouvements GNR liés
        movements_cancelled = cancel_related_gnr_movements(doctype, name)
        
        # 2. Annuler la facture
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus != 1:
            frappe.throw(_("Le document doit être soumis pour être annulé"))
        
        doc.cancel()
        
        # 3. Nettoyer les brouillons restants
        cleanup_draft_movements(doctype, name)
        
        return {
            "success": True,
            "message": f"✅ Document {name} annulé avec {movements_cancelled} mouvement(s) GNR",
            "movements_cancelled": movements_cancelled
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur annulation {doctype} {name}: {str(e)}")
        return {
            "success": False,
            "message": f"❌ Erreur: {str(e)}"
        }

@frappe.whitelist()
def cancel_related_gnr_movements(doctype, name):
    """
    Annule tous les mouvements GNR liés à un document
    
    Returns:
        int: Nombre de mouvements annulés
    """
    movements = frappe.get_all("Mouvement GNR",
                              filters={
                                  "reference_document": doctype,
                                  "reference_name": name,
                                  "docstatus": 1  # Seulement les soumis
                              })
    
    movements_cancelled = 0
    for movement in movements:
        try:
            mov_doc = frappe.get_doc("Mouvement GNR", movement.name)
            mov_doc.cancel()
            movements_cancelled += 1
            
        except Exception as e:
            frappe.log_error(f"Erreur annulation mouvement {movement.name}: {str(e)}")
            frappe.throw(f"Impossible d'annuler le mouvement GNR {movement.name}: {str(e)}")
    
    return movements_cancelled

def cleanup_draft_movements(doctype, name):
    """
    Supprime les mouvements GNR en brouillon restants
    """
    draft_movements = frappe.get_all("Mouvement GNR",
                                    filters={
                                        "reference_document": doctype,
                                        "reference_name": name,
                                        "docstatus": 0  # Brouillons seulement
                                    })
    
    for movement in draft_movements:
        frappe.delete_doc("Mouvement GNR", movement.name, force=1)

@frappe.whitelist()
def get_gnr_movements_for_document(doctype, name):
    """
    Récupère tous les mouvements GNR liés à un document
    
    Returns:
        list: Liste des mouvements GNR
    """
    return frappe.get_all("Mouvement GNR",
                         filters={
                             "reference_document": doctype,
                             "reference_name": name
                         },
                         fields=["name", "docstatus", "type_mouvement", "quantite", "creation"])

# === FONCTIONS UTILITAIRES POUR LA CONSOLE ===


@frappe.whitelist()
def force_cancel_document(doctype, name):
    """
    Force l'annulation d'un document en ignorant les liens
    ATTENTION: À utiliser avec précaution
    """
    try:
        doc = frappe.get_doc(doctype, name)
        
        # Forcer l'annulation
        doc.flags.ignore_links = True
        doc.cancel()
        
        return {
            "success": True,
            "message": f"Document {name} annulé en mode forcé"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }