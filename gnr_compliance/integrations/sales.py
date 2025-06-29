# gnr_compliance/integrations/sales.py
import frappe
from frappe import _
from frappe.utils import getdate
from gnr_compliance.utils.unit_conversions import convert_to_litres, get_item_unit

# Groupes d'articles GNR valides
GNR_ITEM_GROUPS = [
    "Combustibles/Carburants/GNR",
    "Combustibles/Carburants/Gazole", 
    "Combustibles/Adblue",
    "Combustibles/Fioul/Bio",
    "Combustibles/Fioul/Hiver",
    "Combustibles/Fioul/Standard"
]

def check_if_gnr_item_for_sales(item_code):
    """
    Vérifie si un article est GNR basé sur le groupe d'article
    Uniforme avec la détection des Stock Entry
    """
    try:
        # Méthode 1 : Vérifier le champ is_gnr_tracked
        is_tracked = frappe.get_value("Item", item_code, "is_gnr_tracked")
        if is_tracked:
            return True
        
        # Méthode 2 : Vérifier le groupe d'article
        item_group = frappe.get_value("Item", item_code, "item_group")
        
        if item_group in GNR_ITEM_GROUPS:
            # Marquer automatiquement comme GNR
            category, tax_rate = get_category_and_rate_from_group(item_group)
            
            try:
                frappe.db.set_value("Item", item_code, {
                    "is_gnr_tracked": 1,
                    "gnr_tracked_category": category,
                    "gnr_tax_rate": tax_rate
                })
                frappe.logger().info(f"[GNR] Article {item_code} marqué automatiquement comme GNR (groupe: {item_group})")
            except:
                pass
                
            return True
        
        return False
        
    except Exception as e:
        frappe.logger().error(f"[GNR] Erreur vérification article {item_code}: {str(e)}")
        return False

def get_category_and_rate_from_group(item_group):
    """Retourne la catégorie et le taux selon le groupe"""
    mapping = {
        "Combustibles/Carburants/GNR": ("GNR", 24.81),
        "Combustibles/Carburants/Gazole": ("GAZOLE", 24.81),
        "Combustibles/Adblue": ("ADBLUE", 0),
        "Combustibles/Fioul/Bio": ("FIOUL_BIO", 3.86),
        "Combustibles/Fioul/Hiver": ("FIOUL_HIVER", 3.86),
        "Combustibles/Fioul/Standard": ("FIOUL_STANDARD", 3.86)
    }
    
    return mapping.get(item_group, ("GNR", 24.81))

def capture_vente_gnr(doc, method):
    """
    Capture automatique des ventes GNR depuis Sales Invoice
    AVEC CONVERSION DES UNITÉS EN LITRES
    """
    
    # ... (gardez les fonctions internes get_quarter_from_date, etc.)
    
    try:
        movements_created = 0
        posting_date = getdate(doc.posting_date)
        
        frappe.logger().info(f"[GNR] Capture vente: {doc.name}, Date: {posting_date}")
        
        for item in doc.items:
            # Vérifier si l'article est tracké GNR
            is_gnr = check_if_gnr_item_for_sales(item.item_code)
            
            if is_gnr:
                # Vérifier si mouvement déjà créé
                existing = frappe.get_all("Mouvement GNR",
                                        filters={
                                            "reference_document": "Sales Invoice",
                                            "reference_name": doc.name,
                                            "code_produit": item.item_code
                                        })
                
                if not existing:
                    # NOUVEAU : Récupérer l'unité de mesure de la ligne de facture
                    item_unit = item.uom or get_item_unit(item.item_code)
                    
                    # NOUVEAU : Convertir la quantité en LITRES
                    quantity_in_litres = convert_to_litres(item.qty, item_unit)
                    
                    # Log de la conversion
                    if item_unit != "L" and item_unit != "l":
                        frappe.logger().info(f"[GNR] Conversion: {item.qty} {item_unit} = {quantity_in_litres} litres")
                    
                    # Obtenir catégorie GNR
                    gnr_category = frappe.get_value("Item", item.item_code, "gnr_tracked_category") or "GNR"
                    
                    # RÉCUPÉRER LE VRAI TAUX GNR (par litre)
                    taux_gnr_reel = get_real_gnr_tax_from_invoice(item, doc)
                    
                    # Calculer le montant de taxe réel EN LITRES
                    montant_taxe_reel = quantity_in_litres * taux_gnr_reel if taux_gnr_reel else 0
                    
                    # Créer le mouvement GNR AVEC QUANTITÉ EN LITRES
                    mouvement = frappe.new_doc("Mouvement GNR")
                    mouvement.update({
                        "type_mouvement": "Vente",
                        "date_mouvement": posting_date,
                        "code_produit": item.item_code,
                        "quantite": quantity_in_litres,  # QUANTITÉ EN LITRES
                        "prix_unitaire": item.rate / (quantity_in_litres / item.qty) if item.qty else item.rate,  # Prix par litre
                        "client": doc.customer,
                        "reference_document": "Sales Invoice",
                        "reference_name": doc.name,
                        "categorie_gnr": gnr_category,
                        "trimestre": get_quarter_from_date(posting_date),
                        "annee": posting_date.year,
                        "semestre": get_semestre_from_date(posting_date),
                        "taux_gnr": taux_gnr_reel,  # Taux par LITRE
                        "montant_taxe_gnr": montant_taxe_reel
                    })
                    
                    # NOUVEAU : Ajouter des champs pour traçabilité
                    mouvement.db_set("custom_original_qty", item.qty)
                    mouvement.db_set("custom_original_uom", item_unit)
                    
                    mouvement.insert(ignore_permissions=True)
                    
                    # Soumettre automatiquement
                    try:
                        mouvement.submit()
                        movements_created += 1
                        frappe.logger().info(f"[GNR] Mouvement créé: {mouvement.name} - {quantity_in_litres}L (depuis {item.qty} {item_unit})")
                    except Exception as submit_error:
                        frappe.log_error(f"Erreur soumission mouvement {mouvement.name}: {str(submit_error)}")
                        movements_created += 1


def capture_achat_gnr(doc, method):
    """
    Capture automatique des achats GNR depuis Purchase Invoice
    RÉCUPÉRATION DES VRAIS TAUX DEPUIS LES FACTURES
    
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
    
    def get_real_gnr_tax_from_purchase(item, doc):
        """Récupère le vrai taux GNR depuis une facture d'achat"""
        try:
            # 1. Chercher dans les taxes de la facture
            if hasattr(doc, 'taxes') and doc.taxes:
                for tax_row in doc.taxes:
                    if tax_row.description:
                        description_lower = tax_row.description.lower()
                        gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant']
                        if any(keyword in description_lower for keyword in gnr_keywords):
                            if item.qty > 0 and tax_row.tax_amount:
                                taux_calcule = abs(tax_row.tax_amount) / item.qty
                                if 0.1 <= taux_calcule <= 50:
                                    return taux_calcule
            
            # 2. Utiliser le taux de l'article
            taux_article = frappe.get_value("Item", item.item_code, "gnr_tax_rate")
            if taux_article and 0.1 <= taux_article <= 50:
                return taux_article
            
            # 3. Historique des achats
            dernier_taux = frappe.db.sql("""
                SELECT taux_gnr 
                FROM `tabMouvement GNR` 
                WHERE code_produit = %s 
                AND type_mouvement = 'Achat'
                AND taux_gnr IS NOT NULL 
                AND taux_gnr > 0.1
                ORDER BY date_mouvement DESC 
                LIMIT 1
            """, (item.item_code,))
            
            if dernier_taux and dernier_taux[0][0]:
                return dernier_taux[0][0]
            
            # 4. Taux par défaut selon le groupe
            item_group = frappe.get_value("Item", item.item_code, "item_group")
            if item_group in GNR_ITEM_GROUPS:
                category, default_rate = get_category_and_rate_from_group(item_group)
                return default_rate
            
            return 0.0
            
        except Exception as e:
            frappe.log_error(f"Erreur récupération taux GNR achat pour {item.item_code}: {str(e)}")
            return 0.0
    
    try:
        movements_created = 0
        posting_date = getdate(doc.posting_date)  # Convertir une seule fois
        
        for item in doc.items:
            # Vérifier si l'article est tracké GNR - UTILISE LA NOUVELLE FONCTION
            is_gnr = check_if_gnr_item_for_sales(item.item_code)  # Même fonction que pour les ventes
            
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
                    gnr_category = frappe.get_value("Item", item.item_code, "gnr_tracked_category") or "GNR"
                    
                    # RÉCUPÉRER LE VRAI TAUX GNR
                    taux_gnr_reel = get_real_gnr_tax_from_purchase(item, doc)
                    
                    # Calculer le montant de taxe réel
                    montant_taxe_reel = item.qty * taux_gnr_reel if taux_gnr_reel else 0
                    
                    # Créer le mouvement GNR
                    mouvement = frappe.new_doc("Mouvement GNR")
                    mouvement.update({
                        "type_mouvement": "Achat",
                        "date_mouvement": posting_date,
                        "code_produit": item.item_code,
                        "quantite": item.qty,
                        "prix_unitaire": item.rate,  # Prix unitaire réel payé
                        "fournisseur": doc.supplier,
                        "reference_document": "Purchase Invoice",
                        "reference_name": doc.name,
                        "categorie_gnr": gnr_category,
                        "trimestre": get_quarter_from_date(posting_date),
                        "annee": posting_date.year,
                        "semestre": get_semestre_from_date(posting_date),
                        "taux_gnr": taux_gnr_reel,  # TAUX RÉEL
                        "montant_taxe_gnr": montant_taxe_reel  # MONTANT RÉEL
                    })
                    
                    mouvement.insert(ignore_permissions=True)
                    
                    # Soumettre automatiquement le mouvement
                    try:
                        mouvement.submit()
                        movements_created += 1
                        frappe.logger().info(f"Mouvement GNR achat créé avec taux réel {taux_gnr_reel}€/L: {mouvement.name} pour facture {doc.name}")
                    except Exception as submit_error:
                        frappe.log_error(f"Erreur soumission mouvement achat {mouvement.name}: {str(submit_error)}")
                        movements_created += 1  # Compter quand même comme créé
        
        if movements_created > 0:
            frappe.msgprint(
                f"✅ {movements_created} mouvement(s) GNR achat créé(s) avec taux réels",
                title="GNR Compliance - Achats",
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
            frappe.logger().info(f"Nettoyage final: {len(remaining)} mouvements GNR restants pour facture {doc.name}")
            
        # Mettre à jour les statuts si nécessaire
        update_gnr_tracking_status(doc, "cancelled")
            
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
            frappe.logger().info(f"Nettoyage final: {len(remaining)} mouvements GNR achat restants pour facture {doc.name}")
            
        # Mettre à jour les statuts si nécessaire
        update_gnr_tracking_status(doc, "cancelled")
            
    except Exception as e:
        frappe.log_error(f"Erreur nettoyage final facture achat {doc.name}: {str(e)}")

def update_gnr_tracking_status(doc, status):
    """Met à jour le statut de suivi GNR pour un document"""
    try:
        # Ajouter un commentaire sur le document pour traçabilité
        doc.add_comment(
            comment_type="Info",
            text=f"Statut GNR mis à jour: {status}"
        )
        
        # Log pour audit
        frappe.logger().info(f"Document {doc.name} - Statut GNR: {status}")
        
    except Exception as e:
        frappe.log_error(f"Erreur mise à jour statut GNR pour {doc.name}: {str(e)}")

@frappe.whitelist()
def get_invoice_gnr_summary(doctype, name):
    """
    Récupère un résumé des mouvements GNR pour une facture
    """
    try:
        movements = frappe.get_all("Mouvement GNR",
                                 filters={
                                     "reference_document": doctype,
                                     "reference_name": name
                                 },
                                 fields=[
                                     "name", "docstatus", "type_mouvement", 
                                     "quantite", "taux_gnr", "montant_taxe_gnr",
                                     "creation", "modified"
                                 ],
                                 order_by="creation desc")
        
        # Calculer les totaux réels
        total_tax = sum([m.montant_taxe_gnr or 0 for m in movements if m.docstatus == 1])
        total_qty = sum([m.quantite or 0 for m in movements if m.docstatus == 1])
        avg_rate = total_tax / total_qty if total_qty > 0 else 0
        
        summary = {
            "total_movements": len(movements),
            "active_movements": len([m for m in movements if m.docstatus == 1]),
            "cancelled_movements": len([m for m in movements if m.docstatus == 2]),
            "draft_movements": len([m for m in movements if m.docstatus == 0]),
            "total_tax_real": total_tax,
            "total_quantity": total_qty,
            "average_rate_real": avg_rate,
            "movements": movements
        }
        
        return summary
        
    except Exception as e:
        frappe.log_error(f"Erreur récupération résumé GNR pour {doctype} {name}: {str(e)}")
        return {"error": str(e)}

@frappe.whitelist()
def validate_cancellation_allowed(doctype, name):
    """
    Vérifie si l'annulation d'un document est autorisée
    """
    try:
        # Vérifier les permissions
        if not frappe.has_permission(doctype, "cancel"):
            return {
                "allowed": False,
                "reason": "Permissions insuffisantes"
            }
        
        # Vérifier le statut du document
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus != 1:
            return {
                "allowed": False,
                "reason": "Le document doit être soumis"
            }
        
        # Vérifier les mouvements GNR
        gnr_movements = frappe.get_all("Mouvement GNR",
                                     filters={
                                         "reference_document": doctype,
                                         "reference_name": name,
                                         "docstatus": 1
                                     })
        
        if gnr_movements:
            return {
                "allowed": False,
                "reason": f"{len(gnr_movements)} mouvement(s) GNR actif(s)",
                "gnr_movements": gnr_movements,
                "suggest_gnr_cancel": True
            }
        
        return {
            "allowed": True,
            "reason": "Annulation autorisée"
        }
        
    except Exception as e:
        return {
            "allowed": False,
            "reason": f"Erreur de validation: {str(e)}"
        }