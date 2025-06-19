# gnr_compliance/doctype/mouvement_gnr/mouvement_gnr.py
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate, get_quarter, flt
from frappe import _

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
        
        # Validation de la quantité
        if not self.quantite or self.quantite <= 0:
            frappe.throw("La quantité doit être supérieure à zéro")
        
        # Validation du taux de taxe si spécifié
        if self.taux_gnr and self.taux_gnr < 0:
            frappe.throw("Le taux GNR ne peut pas être négatif")
    
    def calculer_taxes_gnr(self):
        """Calcul des taxes GNR selon la réglementation"""
        if self.quantite and self.taux_gnr:
            self.montant_taxe_gnr = flt(self.quantite) * flt(self.taux_gnr)
            
            # Calculer le montant total si prix unitaire disponible
            if self.prix_unitaire:
                montant_ht = flt(self.prix_unitaire) * flt(self.quantite)
                self.montant_total = montant_ht + flt(self.montant_taxe_gnr)
        else:
            self.montant_taxe_gnr = 0
    
    def definir_periode_declaration(self):
        """Définir la période de déclaration (trimestrielle/semestrielle)"""
        if not self.date_mouvement:
            return
            
        # Convertir en objet date si c'est une chaîne
        date_mouvement = getdate(self.date_mouvement)
        
        # Définir le trimestre
        self.trimestre = str(get_quarter(date_mouvement))
        self.annee = date_mouvement.year
        
        # Définir le semestre
        self.semestre = "1" if date_mouvement.month <= 6 else "2"
    
    def before_insert(self):
        """Actions avant insertion"""
        # Récupérer automatiquement la catégorie GNR de l'article
        if self.code_produit and not self.categorie_gnr:
            item_data = frappe.get_value("Item", self.code_produit, 
                                       ["gnr_tracked_category", "gnr_tax_rate"],
                                       as_dict=True)
            if item_data:
                if item_data.gnr_tracked_category:
                    self.categorie_gnr = item_data.gnr_tracked_category
                
                if item_data.gnr_tax_rate and not self.taux_gnr:
                    self.taux_gnr = item_data.gnr_tax_rate
    
    def on_submit(self):
        """Actions après validation du mouvement"""
        try:
            self.creer_log_mouvement()
            # self.creer_ecriture_comptable()  # À activer si nécessaire
            # self.mettre_a_jour_stock_gnr()   # À activer si nécessaire
        except Exception as e:
            frappe.log_error(f"Erreur lors de la soumission du mouvement GNR {self.name}: {str(e)}")
    
    def creer_log_mouvement(self):
        """Crée un log dans GNR Movement Log"""
        try:
            if frappe.db.exists("DocType", "GNR Movement Log"):
                log_entry = frappe.new_doc("GNR Movement Log")
                log_entry.update({
                    'reference_doctype': self.doctype,
                    'reference_name': self.name,
                    'item_code': self.code_produit,
                    'gnr_category': self.categorie_gnr,
                    'movement_type': self.type_mouvement,
                    'quantity': flt(self.quantite),
                    'amount': flt(self.montant_taxe_gnr or 0),
                    'user': frappe.session.user,
                    'timestamp': now_datetime(),
                    'details': frappe.as_json({
                        'client': self.client,
                        'fournisseur': self.fournisseur,
                        'prix_unitaire': self.prix_unitaire,
                        'trimestre': self.trimestre,
                        'annee': self.annee
                    })
                })
                log_entry.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Erreur création log mouvement: {str(e)}")
    
    def creer_ecriture_comptable(self):
        """Création automatique des écritures comptables"""
        if not self.montant_taxe_gnr or self.montant_taxe_gnr == 0:
            return
            
        try:
            # Vérifier si les comptes existent
            compte_taxe = frappe.get_value("Account", "Taxes GNR à payer - Société")
            compte_vente = frappe.get_value("Account", "Ventes GNR - Société")
            
            if not compte_taxe or not compte_vente:
                frappe.log_error("Comptes GNR non configurés pour les écritures comptables")
                return
            
            journal_entry = frappe.get_doc({
                "doctype": "Journal Entry",
                "voucher_type": "Journal Entry",
                "posting_date": self.date_mouvement,
                "accounts": [
                    {
                        "account": compte_taxe,
                        "debit_in_account_currency": self.montant_taxe_gnr,
                        "reference_type": self.doctype,
                        "reference_name": self.name
                    },
                    {
                        "account": compte_vente,
                        "credit_in_account_currency": self.montant_taxe_gnr,
                        "reference_type": self.doctype,
                        "reference_name": self.name
                    }
                ]
            })
            journal_entry.insert()
            journal_entry.submit()
            
            frappe.msgprint(f"Écriture comptable créée: {journal_entry.name}")
            
        except Exception as e:
            frappe.log_error(f"Erreur création écriture comptable: {str(e)}")
    
    def mettre_a_jour_stock_gnr(self):
        """Met à jour les stocks GNR si nécessaire"""
        try:
            # Cette fonction peut être implémentée selon les besoins
            # pour maintenir un historique des stocks GNR
            pass
        except Exception as e:
            frappe.log_error(f"Erreur mise à jour stock GNR: {str(e)}")

# Fonctions utilitaires
@frappe.whitelist()
def get_item_gnr_info(item_code):
    """Récupère les informations GNR d'un article"""
    try:
        if not item_code:
            return {}
            
        item_data = frappe.get_value("Item", item_code, 
                                   ["gnr_tracked_category", "gnr_tax_rate", "is_gnr_tracked"],
                                   as_dict=True)
        
        if item_data and item_data.is_gnr_tracked:
            return {
                'category': item_data.gnr_tracked_category,
                'tax_rate': item_data.gnr_tax_rate,
                'is_tracked': True
            }
        else:
            return {'is_tracked': False}
            
    except Exception as e:
        frappe.log_error(f"Erreur récupération info GNR pour {item_code}: {str(e)}")
        return {'is_tracked': False}

@frappe.whitelist()
def calculate_gnr_tax(item_code, quantity):
    """Calcule la taxe GNR pour un article et une quantité donnés"""
    try:
        item_info = get_item_gnr_info(item_code)
        
        if item_info.get('is_tracked') and item_info.get('tax_rate'):
            tax_amount = flt(quantity) * flt(item_info['tax_rate'])
            return {
                'tax_amount': tax_amount,
                'tax_rate': item_info['tax_rate'],
                'category': item_info.get('category')
            }
        else:
            return {'tax_amount': 0, 'tax_rate': 0}
            
    except Exception as e:
        frappe.log_error(f"Erreur calcul taxe GNR: {str(e)}")
        return {'tax_amount': 0, 'tax_rate': 0}