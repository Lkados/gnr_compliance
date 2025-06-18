# gnr_compliance/doctype/mouvement_gnr/mouvement_gnr.py

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate

def get_quarter(date):
    """Retourne le numéro du trimestre (1 à 4) pour une date donnée"""
    date = getdate(date)
    return (date.month - 1) // 3 + 1

class MouvementGNR(Document):
    def validate(self):
        self.valider_donnees_gnr()
        self.calculer_taxes_gnr()
        self.definir_periode_declaration()
    
    def valider_donnees_gnr(self):
        """Validation des données selon les règles GNR"""
        if not self.code_produit:
            frappe.throw("Le code produit GNR est obligatoire")
        
        if self.type_mouvement == "Vente" and not self.client:
            frappe.throw("Client obligatoire pour les ventes GNR")
        
        # Validation du taux de taxe
        taux_valides = frappe.get_all("Taux GNR", 
                                     filters={"applicable": 1},
                                     fields=["taux"])
        if self.taux_gnr not in [t.taux for t in taux_valides]:
            frappe.throw(f"Taux GNR invalide: {self.taux_gnr}")
    
    def calculer_taxes_gnr(self):
        """Calcul des taxes GNR selon la réglementation"""
        if self.quantite and self.taux_gnr:
            self.montant_taxe_gnr = self.quantite * self.taux_gnr
            self.montant_total = self.prix_unitaire * self.quantite + self.montant_taxe_gnr
    
    def definir_periode_declaration(self):
        """Définir la période de déclaration (trimestrielle/semestrielle)"""
        date_mouvement = getdate(self.date_mouvement)
        self.trimestre = get_quarter(date_mouvement)
        self.annee = date_mouvement.year
        self.semestre = 1 if date_mouvement.month <= 6 else 2
    
    def on_submit(self):
        """Actions après validation du mouvement"""
        self.creer_ecriture_comptable()
        self.mettre_a_jour_stock_gnr()
    
    def creer_ecriture_comptable(self):
        """Création automatique des écritures comptables"""
        if self.montant_taxe_gnr > 0:
            journal_entry = frappe.get_doc({
                "doctype": "Journal Entry",
                "voucher_type": "Journal Entry",
                "posting_date": self.date_mouvement,
                "accounts": [
                    {
                        "account": "Taxes GNR à payer - Société",
                        "debit_in_account_currency": self.montant_taxe_gnr,
                        "reference_type": self.doctype,
                        "reference_name": self.name
                    },
                    {
                        "account": "Ventes GNR - Société",
                        "credit_in_account_currency": self.montant_taxe_gnr,
                        "reference_type": self.doctype,
                        "reference_name": self.name
                    }
                ]
            })
            journal_entry.submit()
