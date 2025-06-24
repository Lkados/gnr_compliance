import frappe
from frappe import _
from frappe.utils import getdate

def capture_vente_gnr(doc, method):
    """
    Capture automatique des ventes GNR depuis Sales Invoice
    RÉCUPÉRATION DES VRAIS TAUX DEPUIS LES FACTURES
    
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
    
    def get_real_gnr_tax_from_invoice(item, doc):
        """
        RÉCUPÈRE LE VRAI TAUX DE TAXE GNR DEPUIS LA FACTURE
        Cherche dans les taxes de la facture ou utilise le taux article
        
        Args:
            item: Ligne d'article de la facture
            doc: Document de la facture
            
        Returns:
            float: Taux GNR réel en €/L
        """
        try:
            # 1. Chercher dans les taxes de la facture (Tax and Charges)
            if hasattr(doc, 'taxes') and doc.taxes:
                for tax_row in doc.taxes:
                    if tax_row.description:
                        description_lower = tax_row.description.lower()
                        # Chercher les mots-clés liés à la taxe GNR
                        gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant']
                        if any(keyword in description_lower for keyword in gnr_keywords):
                            # Calculer le taux par litre
                            if item.qty > 0 and tax_row.tax_amount:
                                taux_calcule = abs(tax_row.tax_amount) / item.qty
                                if 0.1 <= taux_calcule <= 50:  # Vérification de cohérence
                                    frappe.logger().info(f"Taux GNR trouvé dans taxes facture {doc.name}: {taux_calcule}€/L")
                                    return taux_calcule
            
            # 2. Chercher dans les champs personnalisés de l'article de la facture
            if hasattr(item, 'gnr_tax_rate') and item.gnr_tax_rate:
                if 0.1 <= item.gnr_tax_rate <= 50:
                    frappe.logger().info(f"Taux GNR trouvé dans item facture: {item.gnr_tax_rate}€/L")
                    return item.gnr_tax_rate
            
            # 3. Utiliser le taux défini sur l'article maître
            taux_article = frappe.get_value("Item", item.item_code, "gnr_tax_rate")
            if taux_article and 0.1 <= taux_article <= 50:
                frappe.logger().info(f"Taux GNR trouvé sur article {item.item_code}: {taux_article}€/L")
                return taux_article
            
            # 4. Chercher le dernier taux utilisé pour ce produit (historique)
            dernier_taux = frappe.db.sql("""
                SELECT taux_gnr 
                FROM `tabMouvement GNR` 
                WHERE code_produit = %s 
                AND taux_gnr IS NOT NULL 
                AND taux_gnr > 0.1
                AND taux_gnr < 50
                ORDER BY date_mouvement DESC 
                LIMIT 1
            """, (item.item_code,))
            
            if dernier_taux and dernier_taux[0][0]:
                taux_historique = dernier_taux[0][0]
                frappe.logger().info(f"Taux GNR trouvé dans historique pour {item.item_code}: {taux_historique}€/L")
                return taux_historique
            
            # 5. Essayer de déduire depuis le prix si aucune taxe explicite
            # Logique métier : si le prix semble inclure la taxe, essayer de la déduire
            if item.rate > 1:  # Prix unitaire > 1€
                # Cette logique dépend de votre structure de prix
                # Exemple : si vous savez que 10% du prix = taxe GNR
                # return item.rate * 0.10
                pass
            
            # Si vraiment rien trouvé, logging d'erreur mais pas de valeur par défaut
            frappe.log_error(f"Aucun taux GNR trouvé pour {item.item_code} dans facture {doc.name}", 
                           "GNR Taux Manquant")
            return 0.0  # Ne pas assumer un taux par défaut
            
        except Exception as e:
            frappe.log_error(f"Erreur récupération taux GNR pour {item.item_code}: {str(e)}")
            return 0.0
    
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
                    gnr_category = frappe.get_value("Item", item.item_code, "gnr_tracked_category") or "GNR"
                    
                    # RÉCUPÉRER LE VRAI TAUX GNR DEPUIS LA FACTURE
                    taux_gnr_reel = get_real_gnr_tax_from_invoice(item, doc)
                    
                    # Calculer le montant de taxe réel
                    montant_taxe_reel = item.qty * taux_gnr_reel if taux_gnr_reel else 0
                    
                    # Créer le mouvement GNR AVEC LES VRAIS TAUX
                    mouvement = frappe.new_doc("Mouvement GNR")
                    mouvement.update({
                        "type_mouvement": "Vente",
                        "date_mouvement": posting_date,
                        "code_produit": item.item_code,
                        "quantite": item.qty,
                        "prix_unitaire": item.rate,  # Prix unitaire réel facturé
                        "client": doc.customer,
                        "reference_document": "Sales Invoice",
                        "reference_name": doc.name,
                        "categorie_gnr": gnr_category,
                        "trimestre": get_quarter_from_date(posting_date),
                        "annee": posting_date.year,
                        "semestre": get_semestre_from_date(posting_date),
                        "taux_gnr": taux_gnr_reel,  # TAUX RÉEL RÉCUPÉRÉ
                        "montant_taxe_gnr": montant_taxe_reel  # MONTANT RÉEL CALCULÉ
                    })
                    
                    mouvement.insert(ignore_permissions=True)
                    
                    # Soumettre automatiquement le mouvement
                    try:
                        mouvement.submit()
                        movements_created += 1
                        frappe.logger().info(f"Mouvement GNR créé avec taux réel {taux_gnr_reel}€/L: {mouvement.name} pour facture {doc.name}")
                    except Exception as submit_error:
                        frappe.log_error(f"Erreur soumission mouvement {mouvement.name}: {str(submit_error)}")
                        movements_created += 1  # Compter quand même comme créé
        
        if movements_created > 0:
            # Message informatif avec détails sur les taux récupérés
            total_tax = sum([
                frappe.get_value("Mouvement GNR", m.name, "montant_taxe_gnr") or 0
                for m in frappe.get_all("Mouvement GNR", {
                    "reference_document": "Sales Invoice",
                    "reference_name": doc.name
                })
            ])
            
            frappe.msgprint(
                f"✅ {movements_created} mouvement(s) GNR créé(s) avec taux réels (Total taxe: {total_tax:.2f}€)",
                title="GNR Compliance - Taux Réels",
                indicator="green"
            )
            
    except Exception as e:
        frappe.log_error(f"Erreur capture GNR pour facture {doc.name}: {str(e)}")
        frappe.throw(_("Erreur lors de la création des mouvements GNR: {0}").format(str(e)))


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
            
            return 0.0
            
        except Exception as e:
            frappe.log_error(f"Erreur récupération taux GNR achat pour {item.item_code}: {str(e)}")
            return 0.0
    
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