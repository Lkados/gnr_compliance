import frappe
from frappe import _

def capture_vente_gnr(doc, method):
    """
    Capture automatique des ventes GNR depuis Sales Invoice
    
    Args:
        doc: Document Sales Invoice
        method: Méthode appelée (on_submit, etc.)
    """
    
    def get_quarter_from_date(date):
        """Calcule le trimestre à partir d'une date"""
        month = date.month
        if month <= 3: 
            return "1"
        elif month <= 6: 
            return "2"
        elif month <= 9: 
            return "3"
        else: 
            return "4"
    
    def get_gnr_tax_rate(gnr_category):
        """Retourne le taux de taxe GNR selon la catégorie"""
        rates = {
            "fioul domestique": 1.77,
            "gasoil": 3.86,
            "essence": 6.83,
            "gpl": 2.84
        }
        
        category_lower = gnr_category.lower()
        for key, rate in rates.items():
            if key in category_lower:
                return rate
        
        return 1.77  # Taux par défaut pour fioul domestique
    
    try:
        movements_created = 0
        
        for item in doc.items:
            # Vérifier si l'article est tracké GNR
            is_gnr = frappe.get_value("Item", item.item_code, "is_gnr_tracked")
            
            if is_gnr:
                # Vérifier si mouvement déjà créé
                existing = frappe.get_all("Mouvement GNR",
                                        filters={
                                            "reference_document": "Sales Invoice",
                                            "reference_name": doc.name,
                                            "code_produit": item.item_code
                                        })
                
                if not existing:
                    # Obtenir catégorie GNR
                    gnr_category = frappe.get_value("Item", item.item_code, "gnr_tracked_category") or "Fioul Domestique"
                    
                    # Calculer taux GNR
                    taux_gnr = get_gnr_tax_rate(gnr_category)
                    
                    # Créer le mouvement GNR
                    mouvement = frappe.new_doc("Mouvement GNR")
                    mouvement.update({
                        "type_mouvement": "Vente",
                        "date_mouvement": doc.posting_date,
                        "code_produit": item.item_code,
                        "quantite": item.qty,
                        "prix_unitaire": item.rate,
                        "client": doc.customer,
                        "reference_document": "Sales Invoice",
                        "reference_name": doc.name,
                        "categorie_gnr": gnr_category,
                        "trimestre": get_quarter_from_date(doc.posting_date),
                        "annee": doc.posting_date.year,
                        "taux_gnr": taux_gnr,
                        "montant_taxe_gnr": item.qty * taux_gnr
                    })
                    
                    mouvement.insert(ignore_permissions=True)
                    movements_created += 1
                    
                    # Log pour debug
                    frappe.logger().info(f"Mouvement GNR créé: {mouvement.name} pour facture {doc.name}")
        
        if movements_created > 0:
            frappe.msgprint(
                f"✅ {movements_created} mouvement(s) GNR créé(s) automatiquement",
                title="GNR Compliance",
                indicator="green"
            )
            
    except Exception as e:
        frappe.log_error(f"Erreur capture GNR pour facture {doc.name}: {str(e)}")
        frappe.throw(_("Erreur lors de la création des mouvements GNR: {0}").format(str(e)))


def capture_achat_gnr(doc, method):
    """
    Capture automatique des achats GNR depuis Purchase Invoice
    
    Args:
        doc: Document Purchase Invoice
        method: Méthode appelée (on_submit, etc.)
    """
    
    def get_quarter_from_date(date):
        """Calcule le trimestre à partir d'une date"""
        month = date.month
        if month <= 3: return "1"
        elif month <= 6: return "2"
        elif month <= 9: return "3"
        else: return "4"
    
    try:
        movements_created = 0
        
        for item in doc.items:
            # Vérifier si l'article est tracké GNR
            is_gnr = frappe.get_value("Item", item.item_code, "is_gnr_tracked")
            
            if is_gnr:
                # Vérifier si mouvement déjà créé
                existing = frappe.get_all("Mouvement GNR",
                                        filters={
                                            "reference_document": "Purchase Invoice",
                                            "reference_name": doc.name,
                                            "code_produit": item.item_code
                                        })
                
                if not existing:
                    # Obtenir catégorie GNR
                    gnr_category = frappe.get_value("Item", item.item_code, "gnr_tracked_category") or "Non classé"
                    
                    # Créer le mouvement GNR
                    mouvement = frappe.new_doc("Mouvement GNR")
                    mouvement.update({
                        "type_mouvement": "Achat",
                        "date_mouvement": doc.posting_date,
                        "code_produit": item.item_code,
                        "quantite": item.qty,
                        "prix_unitaire": item.rate,
                        "fournisseur": doc.supplier,
                        "reference_document": "Purchase Invoice",
                        "reference_name": doc.name,
                        "categorie_gnr": gnr_category,
                        "trimestre": get_quarter_from_date(doc.posting_date),
                        "annee": doc.posting_date.year
                    })
                    
                    mouvement.insert(ignore_permissions=True)
                    movements_created += 1
                    
                    frappe.logger().info(f"Mouvement GNR achat créé: {mouvement.name} pour facture {doc.name}")
        
        if movements_created > 0:
            frappe.msgprint(
                f"✅ {movements_created} mouvement(s) GNR achat créé(s) automatiquement",
                title="GNR Compliance",
                indicator="green"
            )
            
    except Exception as e:
        frappe.log_error(f"Erreur capture GNR achat pour facture {doc.name}: {str(e)}")
        frappe.msgprint(_("Erreur lors de la création des mouvements GNR achat: {0}").format(str(e)))


def cancel_vente_gnr(doc, method):
    """
    Annule les mouvements GNR lors de l'annulation d'une facture de vente
    
    Args:
        doc: Document Sales Invoice annulé
        method: Méthode appelée (on_cancel)
    """
    try:
        # Trouver les mouvements GNR liés à cette facture
        movements = frappe.get_all("Mouvement GNR",
                                  filters={
                                      "reference_document": "Sales Invoice",
                                      "reference_name": doc.name,
                                      "docstatus": ["!=", 2]  # Pas déjà annulés
                                  })
        
        movements_cancelled = 0
        for movement in movements:
            mov_doc = frappe.get_doc("Mouvement GNR", movement.name)
            if mov_doc.docstatus == 1:  # Si soumis, annuler
                mov_doc.cancel()
            else:  # Si brouillon, supprimer
                mov_doc.delete()
            movements_cancelled += 1
        
        if movements_cancelled > 0:
            frappe.msgprint(
                f"✅ {movements_cancelled} mouvement(s) GNR annulé(s)",
                title="GNR Compliance",
                indicator="orange"
            )
            
    except Exception as e:
        frappe.log_error(f"Erreur annulation GNR pour facture {doc.name}: {str(e)}")


def cancel_achat_gnr(doc, method):
    """
    Annule les mouvements GNR lors de l'annulation d'une facture d'achat
    
    Args:
        doc: Document Purchase Invoice annulé
        method: Méthode appelée (on_cancel)
    """
    try:
        # Trouver les mouvements GNR liés à cette facture
        movements = frappe.get_all("Mouvement GNR",
                                  filters={
                                      "reference_document": "Purchase Invoice",
                                      "reference_name": doc.name,
                                      "docstatus": ["!=", 2]  # Pas déjà annulés
                                  })
        
        movements_cancelled = 0
        for movement in movements:
            mov_doc = frappe.get_doc("Mouvement GNR", movement.name)
            if mov_doc.docstatus == 1:  # Si soumis, annuler
                mov_doc.cancel()
            else:  # Si brouillon, supprimer
                mov_doc.delete()
            movements_cancelled += 1
        
        if movements_cancelled > 0:
            frappe.msgprint(
                f"✅ {movements_cancelled} mouvement(s) GNR achat annulé(s)",
                title="GNR Compliance",
                indicator="orange"
            )
            
    except Exception as e:
        frappe.log_error(f"Erreur annulation GNR achat pour facture {doc.name}: {str(e)}")