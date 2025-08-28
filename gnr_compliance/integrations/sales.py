# gnr_compliance/integrations/sales.py
import frappe
from frappe import _
from frappe.utils import getdate, flt
from gnr_compliance.utils.unit_conversions import convert_to_litres, get_item_unit
from gnr_compliance.utils.date_utils import get_quarter_from_date, get_semestre_from_date
import re

def determine_customer_category_from_attestation(customer_code):
    """
    Détermine la catégorie du client basée sur son attestation d'accise
    
    Args:
        customer_code: Code du client
        
    Returns:
        str: "Agricole" si attestation complète, "Autre" sinon
    """
    try:
        # Récupérer les champs d'attestation du client
        customer_data = frappe.db.get_value(
            "Customer", 
            customer_code, 
            ["custom_n_dossier_", "custom_date_de_depot"], 
            as_dict=True
        )
        
        if customer_data:
            # Vérifier si l'attestation est complète (numéro ET date)
            has_complete_attestation = (
                customer_data.get('custom_n_dossier_') and 
                str(customer_data.get('custom_n_dossier_', '')).strip() != '' and
                customer_data.get('custom_date_de_depot')
            )
            
            if has_complete_attestation:
                frappe.logger().info(f"[GNR] Client {customer_code} avec attestation complète → Catégorie Agricole (3.86€/hL)")
                return "Agricole"
            else:
                frappe.logger().info(f"[GNR] Client {customer_code} sans attestation complète → Catégorie Autre (24.81€/hL)")
                return "Autre"
        else:
            frappe.logger().warning(f"[GNR] Client {customer_code} non trouvé → Catégorie Autre par défaut")
            return "Autre"
            
    except Exception as e:
        frappe.log_error(f"Erreur détermination catégorie client {customer_code}: {str(e)}")
        return "Autre"

def get_tax_rate_from_customer_category(customer_category):
    """
    Retourne le taux de taxe basé sur la catégorie client
    
    Args:
        customer_category: "Agricole" ou "Autre"
        
    Returns:
        float: Taux en €/hL
    """
    if customer_category == "Agricole":
        return 3.86  # Taux réduit avec attestation
    else:
        return 24.81  # Taux standard sans attestation




def get_historical_rate_for_item(item_code):
    """Récupère le taux historique le plus récent pour un article"""
    try:
        result = frappe.db.sql(
            """
            SELECT taux_gnr 
            FROM `tabMouvement GNR` 
            WHERE code_produit = %s 
            AND taux_gnr IS NOT NULL 
            AND taux_gnr > 0.1
            AND taux_gnr < 50
            AND docstatus = 1
            ORDER BY date_mouvement DESC, creation DESC
            LIMIT 1
        """,
            (item_code,),
        )

        return result[0][0] if result else None
    except:
        return None


def get_real_gnr_tax_from_invoice(item, invoice_doc):
    """
    RÉCUPÈRE LE VRAI TAUX GNR DEPUIS UNE FACTURE

    Args:
        item: Ligne d'article de la facture
        invoice_doc: Document facture (Sales Invoice ou Purchase Invoice)

    Returns:
        float: Taux GNR réel en €/L
    """
    try:
        # 1. PRIORITÉ 1: Chercher dans les taxes de la facture
        if hasattr(invoice_doc, "taxes") and invoice_doc.taxes:
            for tax_row in invoice_doc.taxes:
                if tax_row.description:
                    description_lower = tax_row.description.lower()
                    # Mots-clés pour identifier les taxes GNR
                    gnr_keywords = [
                        "gnr",
                        "accise",
                        "ticpe",
                        "gazole",
                        "fioul",
                        "carburant",
                        "tipp",
                        "diesel",
                    ]

                    if any(keyword in description_lower for keyword in gnr_keywords):
                        if item.qty > 0 and tax_row.tax_amount:
                            # Convertir la quantité en litres si nécessaire
                            item_unit = item.uom or get_item_unit(item.item_code)
                            quantity_in_litres = convert_to_litres(item.qty, item_unit)

                            if quantity_in_litres > 0:
                                taux_calcule = (
                                    abs(tax_row.tax_amount) / quantity_in_litres
                                )
                                # Vérification de cohérence (taux entre 0.1 et 50 €/L)
                                if 0.1 <= taux_calcule <= 50:
                                    frappe.logger().info(
                                        f"[GNR] Taux RÉEL trouvé dans taxes facture {invoice_doc.name}: {taux_calcule}€/L (taxe: {tax_row.tax_amount}€ / {quantity_in_litres}L)"
                                    )
                                    return taux_calcule

        # 2. PRIORITÉ 2: Chercher dans un champ personnalisé de l'item
        if hasattr(item, "gnr_tax_rate") and item.gnr_tax_rate:
            if 0.1 <= item.gnr_tax_rate <= 50:
                frappe.logger().info(
                    f"[GNR] Taux trouvé dans champ item facture: {item.gnr_tax_rate}€/L"
                )
                return item.gnr_tax_rate

        # 3. PRIORITÉ 3: Chercher dans les termes/commentaires de la facture
        if hasattr(invoice_doc, "terms") and invoice_doc.terms:
            # Patterns pour chercher "3.86€/L", "taxe 2.84", etc.
            patterns = [
                r"(\d+[.,]\d+)\s*[€]\s*[/]\s*[Ll]",  # "3.86€/L"
                r"taxe[:\s]+(\d+[.,]\d+)",  # "taxe: 3.86"
                r"tipp[:\s]+(\d+[.,]\d+)",  # "tipp: 3.86"
                r"accise[:\s]+(\d+[.,]\d+)",  # "accise: 3.86"
                r"gnr[:\s]+(\d+[.,]\d+)",  # "gnr: 3.86"
            ]

            for pattern in patterns:
                matches = re.findall(pattern, invoice_doc.terms, re.IGNORECASE)
                if matches:
                    for match in matches:
                        taux_potentiel = float(match.replace(",", "."))
                        if 0.1 <= taux_potentiel <= 50:
                            frappe.logger().info(
                                f"[GNR] Taux trouvé dans termes facture: {taux_potentiel}€/L"
                            )
                            return taux_potentiel

        # 4. PRIORITÉ 4: Chercher dans l'historique des mouvements de cet article
        historical_rate = get_historical_rate_for_item(item.item_code)
        if historical_rate and 0.1 <= historical_rate <= 50:
            frappe.logger().info(f"[GNR] Taux historique utilisé: {historical_rate}€/L")
            return historical_rate

        # 5. PRIORITÉ 5: Utiliser le taux défini sur l'article maître
        item_rate = frappe.get_value("Item", item.item_code, "gnr_tax_rate")
        if item_rate and 0.1 <= item_rate <= 50:
            frappe.logger().info(f"[GNR] Taux article maître utilisé: {item_rate}€/L")
            return item_rate

        # 6. DERNIER RECOURS: Utiliser le taux basé sur l'attestation du client
        try:
            customer_category = determine_customer_category_from_attestation(invoice_doc.customer)
            fallback_rate = get_tax_rate_from_customer_category(customer_category)
            frappe.logger().warning(
                f"[GNR] Aucun taux réel trouvé pour {item.item_code}, utilisation taux basé sur attestation client: {fallback_rate}€/L (catégorie: {customer_category})"
            )
            return fallback_rate
        except:
            # Si même la récupération de l'attestation échoue, taux standard par défaut
            default_rate = 24.81
            frappe.logger().warning(
                f"[GNR] Aucun taux trouvé pour {item.item_code}, utilisation taux standard par défaut: {default_rate}€/L"
            )
            return default_rate

    except Exception as e:
        frappe.log_error(
            f"Erreur récupération taux réel pour {item.item_code}: {str(e)}"
        )
        return 0.0

def check_if_gnr_item_for_sales(item_code):
    """
    Vérifie si un article est GNR basé UNIQUEMENT sur le marquage manuel
    """
    try:
        # Vérifier uniquement le champ is_gnr_tracked
        is_tracked = frappe.get_value("Item", item_code, "is_gnr_tracked")
        return bool(is_tracked)

    except Exception as e:
        frappe.logger().error(
            f"[GNR] Erreur vérification article {item_code}: {str(e)}"
        )
        return False

def capture_vente_gnr(doc, method):
    """
    Capture automatique des ventes GNR depuis Sales Invoice
    AVEC RÉCUPÉRATION DES VRAIS TAUX DEPUIS LES FACTURES
    """

    try:
        movements_created = 0
        posting_date = getdate(doc.posting_date)

        frappe.logger().info(
            f"[GNR] Capture vente avec VRAIS TAUX: {doc.name}, Date: {posting_date}"
        )

        for item in doc.items:
            # Vérifier si l'article est tracké GNR
            is_gnr = check_if_gnr_item_for_sales(item.item_code)

            if is_gnr:
                # Vérifier si mouvement déjà créé
                existing = frappe.get_all(
                    "Mouvement GNR",
                    filters={
                        "reference_document": "Sales Invoice",
                        "reference_name": doc.name,
                        "code_produit": item.item_code,
                    },
                )

                if not existing:
                    # Récupérer l'unité de mesure de la ligne de facture
                    item_unit = item.uom or get_item_unit(item.item_code)

                    # Convertir la quantité en LITRES
                    quantity_in_litres = convert_to_litres(item.qty, item_unit)

                    # Log de la conversion avec prix
                    if item_unit != "L" and item_unit != "l":
                        prix_unitaire_original = item.rate / item.qty if item.qty else 0
                        frappe.logger().info(
                            f"[GNR] Conversion: {item.qty} {item_unit} = {quantity_in_litres} litres"
                        )
                        frappe.logger().info(
                            f"[GNR] Prix: {prix_unitaire_original:.2f}€/{item_unit} → {prix_unitaire_par_litre:.4f}€/L"
                        )

                    # Déterminer la catégorie client basée sur l'attestation d'accise
                    customer_category = determine_customer_category_from_attestation(doc.customer)
                    
                    # Catégorie GNR fixe (un seul type)
                    gnr_category = "GNR"

                    # RÉCUPÉRER LE VRAI TAUX GNR DEPUIS LA FACTURE
                    taux_gnr_reel = get_real_gnr_tax_from_invoice(item, doc)

                    # Calculer le montant de taxe réel EN LITRES
                    montant_taxe_reel = (
                        quantity_in_litres * taux_gnr_reel if taux_gnr_reel else 0
                    )

                    # Prix unitaire par litre (depuis le prix total de la ligne facture)
                    if item.qty and quantity_in_litres > 0:
                        prix_unitaire_par_litre = item.rate / (quantity_in_litres / item.qty)
                    else:
                        prix_unitaire_par_litre = item.rate
                    
                    # Validation du prix calculé
                    if prix_unitaire_par_litre <= 0:
                        frappe.logger().warning(f"[GNR] Prix par litre invalide: {prix_unitaire_par_litre}€/L pour {item.item_code}")
                        prix_unitaire_par_litre = 0

                    # Créer le mouvement GNR AVEC QUANTITÉ EN LITRES
                    mouvement = frappe.new_doc("Mouvement GNR")
                    mouvement.update(
                        {
                            "type_mouvement": "Vente",
                            "date_mouvement": posting_date,
                            "code_produit": item.item_code,
                            "quantite": quantity_in_litres,  # QUANTITÉ EN LITRES
                            "prix_unitaire": prix_unitaire_par_litre,  # Prix par litre
                            "client": doc.customer,
                            "customer_category": customer_category,  # CATÉGORIE POUR AFFICHAGE ET EXPORT
                            "reference_document": "Sales Invoice",
                            "reference_name": doc.name,
                            "categorie_gnr": gnr_category,
                            "trimestre": get_quarter_from_date(posting_date),
                            "annee": posting_date.year,
                            "semestre": get_semestre_from_date(posting_date),
                            "taux_gnr": taux_gnr_reel,  # TAUX RÉEL CALCULÉ DEPUIS LA FACTURE
                            "montant_taxe_gnr": montant_taxe_reel,  # MONTANT RÉEL CALCULÉ DEPUIS LA FACTURE
                        }
                    )

                    # Ajouter des champs pour traçabilité
                    mouvement.db_set("custom_original_qty", item.qty)
                    mouvement.db_set("custom_original_uom", item_unit)
                    mouvement.db_set("custom_tax_source", "Analyse facture automatique")

                    mouvement.insert(ignore_permissions=True)

                    # Soumettre automatiquement
                    try:
                        mouvement.submit()
                        movements_created += 1
                        frappe.logger().info(
                            f"[GNR] Mouvement créé avec TAUX RÉEL: {mouvement.name} - {quantity_in_litres}L à {taux_gnr_reel}€/L = {montant_taxe_reel}€"
                        )
                    except Exception as submit_error:
                        frappe.log_error(
                            f"Erreur soumission mouvement {mouvement.name}: {str(submit_error)}"
                        )
                        movements_created += 1

        if movements_created > 0:
            frappe.msgprint(
                f"✅ {movements_created} mouvement(s) GNR créé(s) avec TAUX RÉELS depuis facture",
                title="GNR Compliance - Ventes",
                indicator="green",
            )

    except Exception as e:
        frappe.log_error(
            f"Erreur capture GNR vente avec taux réels pour facture {doc.name}: {str(e)}"
        )
        frappe.msgprint(
            _("Erreur lors de la création des mouvements GNR: {0}").format(str(e))
        )

def capture_achat_gnr(doc, method):
    """
    Capture automatique des achats GNR depuis Purchase Invoice
    AVEC RÉCUPÉRATION DES VRAIS TAUX DEPUIS LES FACTURES D'ACHAT

    Args:
        doc: Document Purchase Invoice
        method: Méthode appelée (on_submit, etc.)
    """

    try:
        movements_created = 0
        posting_date = getdate(doc.posting_date)  # Convertir une seule fois

        frappe.logger().info(
            f"[GNR] Capture achat avec VRAIS TAUX: {doc.name}, Date: {posting_date}"
        )

        for item in doc.items:
            # Vérifier si l'article est tracké GNR
            is_gnr = check_if_gnr_item_for_sales(
                item.item_code
            )  # Même fonction que pour les ventes

            if is_gnr:
                # Vérifier si mouvement déjà créé
                existing = frappe.get_all(
                    "Mouvement GNR",
                    filters={
                        "reference_document": "Purchase Invoice",
                        "reference_name": doc.name,
                        "code_produit": item.item_code,
                    },
                )

                if not existing:
                    # Convertir en litres
                    item_unit = item.uom or get_item_unit(item.item_code)
                    quantity_in_litres = convert_to_litres(item.qty, item_unit)

                    # Déterminer la catégorie client basée sur l'attestation d'accise
                    customer_category = determine_customer_category_from_attestation(doc.customer)
                    
                    # Catégorie GNR fixe (un seul type)
                    gnr_category = "GNR"

                    # RÉCUPÉRER LE VRAI TAUX GNR DEPUIS LA FACTURE D'ACHAT
                    taux_gnr_reel = get_real_gnr_tax_from_invoice(item, doc)

                    # Calculer le montant de taxe réel
                    montant_taxe_reel = (
                        quantity_in_litres * taux_gnr_reel if taux_gnr_reel else 0
                    )

                    # Prix unitaire par litre (depuis le prix total de la ligne facture)
                    if item.qty and quantity_in_litres > 0:
                        prix_unitaire_par_litre = item.rate / (quantity_in_litres / item.qty)
                    else:
                        prix_unitaire_par_litre = item.rate
                    
                    # Validation du prix calculé
                    if prix_unitaire_par_litre <= 0:
                        frappe.logger().warning(f"[GNR] Prix par litre invalide: {prix_unitaire_par_litre}€/L pour {item.item_code}")
                        prix_unitaire_par_litre = 0

                    # Créer le mouvement GNR
                    mouvement = frappe.new_doc("Mouvement GNR")
                    mouvement.update(
                        {
                            "type_mouvement": "Achat",
                            "date_mouvement": posting_date,
                            "code_produit": item.item_code,
                            "quantite": quantity_in_litres,
                            "prix_unitaire": prix_unitaire_par_litre,  # Prix réel payé par litre
                            "fournisseur": doc.supplier,
                            "reference_document": "Purchase Invoice",
                            "reference_name": doc.name,
                            "categorie_gnr": gnr_category,
                            "trimestre": get_quarter_from_date(posting_date),
                            "annee": posting_date.year,
                            "semestre": get_semestre_from_date(posting_date),
                            "taux_gnr": taux_gnr_reel,  # TAUX RÉEL
                            "montant_taxe_gnr": montant_taxe_reel,  # MONTANT RÉEL
                        }
                    )

                    mouvement.insert(ignore_permissions=True)

                    # Soumettre automatiquement le mouvement
                    try:
                        mouvement.submit()
                        movements_created += 1
                        frappe.logger().info(
                            f"[GNR] Mouvement GNR achat créé avec taux réel {taux_gnr_reel}€/L: {mouvement.name} pour facture {doc.name}"
                        )
                    except Exception as submit_error:
                        frappe.log_error(
                            f"Erreur soumission mouvement achat {mouvement.name}: {str(submit_error)}"
                        )
                        movements_created += 1  # Compter quand même comme créé

        if movements_created > 0:
            frappe.msgprint(
                f"✅ {movements_created} mouvement(s) GNR achat créé(s) avec TAUX RÉELS depuis facture",
                title="GNR Compliance - Achats",
                indicator="green",
            )

    except Exception as e:
        frappe.log_error(
            f"Erreur capture GNR achat avec taux réels pour facture {doc.name}: {str(e)}"
        )
        frappe.msgprint(
            _("Erreur lors de la création des mouvements GNR achat: {0}").format(str(e))
        )

def cancel_vente_gnr(doc, method):
    """
    Annule les mouvements GNR lors de l'annulation d'une facture de vente

    Args:
        doc: Document Sales Invoice annulé
        method: Méthode appelée (on_cancel)
    """
    try:
        # Trouver les mouvements GNR liés à cette facture
        movements = frappe.get_all(
            "Mouvement GNR",
            filters={
                "reference_document": "Sales Invoice",
                "reference_name": doc.name,
                "docstatus": ["!=", 2],  # Pas déjà annulés
            },
        )

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
                indicator="orange",
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
        movements = frappe.get_all(
            "Mouvement GNR",
            filters={
                "reference_document": "Purchase Invoice",
                "reference_name": doc.name,
                "docstatus": ["!=", 2],  # Pas déjà annulés
            },
        )

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
                indicator="orange",
            )

    except Exception as e:
        frappe.log_error(
            f"Erreur annulation GNR achat pour facture {doc.name}: {str(e)}"
        )

def cleanup_after_cancel(doc, method):
    """Nettoyage final après annulation facture de vente"""
    try:
        # Vérifier s'il reste des mouvements non traités
        remaining = frappe.get_all(
            "Mouvement GNR",
            filters={
                "reference_document": "Sales Invoice",
                "reference_name": doc.name,
                "docstatus": ["!=", 2],
            },
        )

        if remaining:
            frappe.logger().info(
                f"Nettoyage final: {len(remaining)} mouvements GNR restants pour facture {doc.name}"
            )

        # Mettre à jour les statuts si nécessaire
        update_gnr_tracking_status(doc, "cancelled")

    except Exception as e:
        frappe.log_error(f"Erreur nettoyage final facture {doc.name}: {str(e)}")

def cleanup_after_cancel_purchase(doc, method):
    """Nettoyage final après annulation facture d'achat"""
    try:
        remaining = frappe.get_all(
            "Mouvement GNR",
            filters={
                "reference_document": "Purchase Invoice",
                "reference_name": doc.name,
                "docstatus": ["!=", 2],
            },
        )

        if remaining:
            frappe.logger().info(
                f"Nettoyage final: {len(remaining)} mouvements GNR achat restants pour facture {doc.name}"
            )

        # Mettre à jour les statuts si nécessaire
        update_gnr_tracking_status(doc, "cancelled")

    except Exception as e:
        frappe.log_error(f"Erreur nettoyage final facture achat {doc.name}: {str(e)}")

def update_gnr_tracking_status(doc, status):
    """Met à jour le statut de suivi GNR pour un document"""
    try:
        # Ajouter un commentaire sur le document pour traçabilité
        doc.add_comment(comment_type="Info", text=f"Statut GNR mis à jour: {status}")

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
        movements = frappe.get_all(
            "Mouvement GNR",
            filters={"reference_document": doctype, "reference_name": name},
            fields=[
                "name",
                "docstatus",
                "type_mouvement",
                "quantite",
                "taux_gnr",
                "montant_taxe_gnr",
                "creation",
                "modified",
            ],
            order_by="creation desc",
        )

        # Calculer les totaux réels
        total_tax = sum(
            [m.montant_taxe_gnr or 0 for m in movements if m.docstatus == 1]
        )
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
            "movements": movements,
        }

        return summary

    except Exception as e:
        frappe.log_error(
            f"Erreur récupération résumé GNR pour {doctype} {name}: {str(e)}"
        )
        return {"error": str(e)}

@frappe.whitelist()
def recalculer_tous_les_taux_reels_factures(limite=100):
    """
    Recalcule tous les mouvements GNR avec des taux suspects en utilisant les vraies factures
    """
    try:
        # Chercher les mouvements avec taux par défaut suspects
        mouvements_suspects = frappe.db.sql(
            """
            SELECT name, code_produit, taux_gnr, reference_document, reference_name, quantite
            FROM `tabMouvement GNR`
            WHERE docstatus = 1
            AND reference_document IN ('Sales Invoice', 'Purchase Invoice')
            AND taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81)  -- Taux suspects par défaut
            ORDER BY creation DESC
            LIMIT %s
        """,
            (limite,),
            as_dict=True,
        )

        corriges = 0
        echecs = 0

        for mouvement in mouvements_suspects:
            try:
                # Récupérer la facture source
                facture = frappe.get_doc(
                    mouvement.reference_document, mouvement.reference_name
                )

                # Trouver l'item correspondant
                for item in facture.items:
                    if item.item_code == mouvement.code_produit:
                        # Recalculer le taux réel
                        nouveau_taux = get_real_gnr_tax_from_invoice(item, facture)

                        if nouveau_taux and nouveau_taux != mouvement.taux_gnr:
                            nouveau_montant = mouvement.quantite * nouveau_taux

                            # Mettre à jour le mouvement
                            frappe.db.set_value(
                                "Mouvement GNR",
                                mouvement.name,
                                {
                                    "taux_gnr": nouveau_taux,
                                    "montant_taxe_gnr": nouveau_montant,
                                },
                            )

                            corriges += 1
                            frappe.logger().info(
                                f"[GNR] Mouvement {mouvement.name} corrigé: {mouvement.taux_gnr} → {nouveau_taux}€/L"
                            )
                            break

            except Exception as e:
                frappe.log_error(
                    f"Erreur correction mouvement {mouvement.name}: {str(e)}"
                )
                echecs += 1

        frappe.db.commit()

        return {
            "success": True,
            "corriges": corriges,
            "echecs": echecs,
            "message": f"{corriges} mouvements corrigés avec vrais taux depuis factures, {echecs} échecs",
            "total_traites": len(mouvements_suspects),
        }

    except Exception as e:
        frappe.log_error(f"Erreur recalcul taux réels depuis factures: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def analyser_qualite_taux_factures():
    """
    Analyse la qualité des taux GNR en distinguant les sources
    """
    try:
        analyse = frappe.db.sql(
            """
            SELECT 
                COUNT(*) as total_mouvements,
                COUNT(CASE WHEN taux_gnr = 0 THEN 1 END) as taux_zero,
                COUNT(CASE WHEN taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as taux_suspects,
                COUNT(CASE WHEN taux_gnr > 0 AND taux_gnr NOT IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as taux_reels,
                COUNT(CASE WHEN reference_document IN ('Sales Invoice', 'Purchase Invoice') THEN 1 END) as avec_facture,
                AVG(CASE WHEN taux_gnr > 0 THEN taux_gnr END) as taux_moyen,
                MIN(CASE WHEN taux_gnr > 0 THEN taux_gnr END) as taux_min,
                MAX(taux_gnr) as taux_max
            FROM `tabMouvement GNR`
            WHERE docstatus = 1
        """,
            as_dict=True,
        )

        if analyse:
            stats = analyse[0]
            total = stats.total_mouvements or 1

            return {
                "success": True,
                "statistiques": {
                    "total_mouvements": stats.total_mouvements,
                    "avec_facture": stats.avec_facture,
                    "taux_zero": stats.taux_zero,
                    "taux_suspects": stats.taux_suspects,
                    "taux_reels": stats.taux_reels,
                    "pourcentage_reels": round((stats.taux_reels / total) * 100, 1),
                    "pourcentage_suspects": round(
                        (stats.taux_suspects / total) * 100, 1
                    ),
                    "pourcentage_avec_facture": round(
                        (stats.avec_facture / total) * 100, 1
                    ),
                    "taux_moyen": round(stats.taux_moyen or 0, 3),
                    "taux_min": stats.taux_min,
                    "taux_max": stats.taux_max,
                },
                "recommandation": get_recommandation_qualite_factures(stats, total),
            }

        return {"success": False, "message": "Aucune donnée trouvée"}

    except Exception as e:
        frappe.log_error(f"Erreur analyse qualité taux factures: {str(e)}")
        return {"success": False, "error": str(e)}

def get_recommandation_qualite_factures(stats, total):
    """Génère une recommandation basée sur la qualité des taux"""
    pourcentage_reels = (stats.taux_reels / total) * 100
    pourcentage_suspects = (stats.taux_suspects / total) * 100

    if pourcentage_reels >= 80:
        return "✅ EXCELLENTE qualité - Plus de 80% des taux sont réels depuis les factures"
    elif pourcentage_reels >= 60:
        return "🟡 BONNE qualité - Plus de 60% des taux sont réels"
    elif pourcentage_suspects > 50:
        return "🔴 MAUVAISE qualité - Plus de 50% des taux sont suspects. Exécutez 'recalculer_tous_les_taux_reels_factures()'"
    else:
        return "🟠 QUALITÉ MOYENNE - Vérifiez et corrigez les taux suspects avec les vraies factures"
