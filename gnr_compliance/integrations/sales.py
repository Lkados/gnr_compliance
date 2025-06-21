import frappe
from frappe import _
from frappe.utils import getdate

def capture_vente_gnr(doc, method):
    """
    Capture automatique des ventes GNR depuis Sales Invoice
    
    Args:
        doc: Document Sales Invoice
        method: Méthode appelée (on_submit, etc.)
    """
    
    def get_quarter_from_date(date_value):
        """Calcule le trimestre à partir d'une date"""
        # Convertir en objet date si c'est une chaîne
        if isinstance(date_value, str):
            date_value = getdate(date_value)
        
        month = date_value.month
        if month <= 3: 
            return "1"
        elif month <= 6: 
            return "2"
        elif month <= 9: 
            return "3"
        else: 
            return "4"
    
    def get_semestre_from_date(date_value):
        """Calcule le semestre à partir d'une date"""
        if isinstance(date_value, str):
            date_value = getdate(date_value)
        
        return "1" if date_value.month <= 6 else "2"
    
    def get_gnr_tax_rate(gnr_category):
        """Retourne le taux de taxe GNR selon la catégorie"""
        rates = {
            "fioul domestique": 1.77,
            "gasoil": 3.86,
            "essence": 6.83,
            "gpl": 2.84,
            "gnr": 3.86,
            "gazole": 3.86,
            "adblue": 0.00  # AdBlue n'est pas taxé
        }
        
        category_lower = gnr_category.lower()
        for key, rate in rates.items():
            if key in category_lower:
                return rate
        
        return 1.77  # Taux par défaut pour fioul domestique
    
    try:
        movements_created = 0
        posting_date = getdate(doc.posting_date)  # Convertir une seule fois
        
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
                        "date_mouvement": posting_date,
                        "code_produit": item.item_code,
                        "quantite": item.qty,
                        "prix_unitaire": item.rate,
                        "client": doc.customer,
                        "reference_document": "Sales Invoice",
                        "reference_name": doc.name,
                        "categorie_gnr": gnr_category,
                        "trimestre": get_quarter_from_date(posting_date),
                        "annee": posting_date.year,
                        "semestre": get_semestre_from_date(posting_date),
                        "taux_gnr": taux_gnr,
                        "montant_taxe_gnr": item.qty * taux_gnr
                    })
                    
                    mouvement.insert(ignore_permissions=True)
                    
                    # Soumettre automatiquement le mouvement
                    try:
                        mouvement.submit()
                        movements_created += 1
                        frappe.logger().info(f"Mouvement GNR créé et soumis: {mouvement.name} pour facture {doc.name}")
                    except Exception as submit_error:
                        frappe.log_error(f"Erreur soumission mouvement {mouvement.name}: {str(submit_error)}")
                        movements_created += 1  # Compter quand même comme créé
        
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
    
    def get_quarter_from_date(date_value):
        """Calcule le trimestre à partir d'une date"""
        if isinstance(date_value, str):
            date_value = getdate(date_value)
        
        month = date_value.month
        if month <= 3: return "1"
        elif month <= 6: return "2"
        elif month <= 9: return "3"
        else: return "4"
    
    def get_semestre_from_date(date_value):
        """Calcule le semestre à partir d'une date"""
        if isinstance(date_value, str):
            date_value = getdate(date_value)
        
        return "1" if date_value.month <= 6 else "2"
    
    try:
        movements_created = 0
        posting_date = getdate(doc.posting_date)  # Convertir une seule fois
        
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
                        "date_mouvement": posting_date,
                        "code_produit": item.item_code,
                        "quantite": item.qty,
                        "prix_unitaire": item.rate,
                        "fournisseur": doc.supplier,
                        "reference_document": "Purchase Invoice",
                        "reference_name": doc.name,
                        "categorie_gnr": gnr_category,
                        "trimestre": get_quarter_from_date(posting_date),
                        "annee": posting_date.year,
                        "semestre": get_semestre_from_date(posting_date)
                    })
                    
                    mouvement.insert(ignore_permissions=True)
                    
                    # Soumettre automatiquement le mouvement
                    try:
                        mouvement.submit()
                        movements_created += 1
                        frappe.logger().info(f"Mouvement GNR achat créé et soumis: {mouvement.name} pour facture {doc.name}")
                    except Exception as submit_error:
                        frappe.log_error(f"Erreur soumission mouvement achat {mouvement.name}: {str(submit_error)}")
                        movements_created += 1  # Compter quand même comme créé
        
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

def cleanup_after_cancel(doc, method):
    """Nettoyage final après annulation facture de vente"""
    try:
        # Vérifier s'il reste des mouvements non traités
        remaining = frappe.get_all("Mouvement GNR",
                                 filters={
                                     "reference_document": "Sales Invoice",
                                     "reference_name": doc.name,
                                     "docstatus": ["!=", 2]
                                 })
        
        if remaining:
            frappe.log_error(f"Mouvements GNR restants après annulation facture {doc.name}: {len(remaining)}")
            
    except Exception as e:
        frappe.log_error(f"Erreur nettoyage final facture {doc.name}: {str(e)}")

def cleanup_after_cancel_purchase(doc, method):
    """Nettoyage final après annulation facture d'achat"""
    try:
        remaining = frappe.get_all("Mouvement GNR",
                                 filters={
                                     "reference_document": "Purchase Invoice", 
                                     "reference_name": doc.name,
                                     "docstatus": ["!=", 2]
                                 })
        
        if remaining:
            frappe.log_error(f"Mouvements GNR achat restants après annulation facture {doc.name}: {len(remaining)}")
            
    except Exception as e:
        frappe.log_error(f"Erreur nettoyage final facture achat {doc.name}: {str(e)}")