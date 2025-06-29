# Copyright (c) 2025, Mohamed Kachtit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate

class MouvementGNR(Document):
    def validate(self):
        """Validation avec calculs automatiques"""
        self.calculer_taux_et_montants()
        self.calculer_periodes()
    
    def calculer_taux_et_montants(self):
        """Calcule automatiquement le taux GNR et le montant de taxe"""
        try:
            # 1. Si pas de taux GNR, essayer de le récupérer depuis l'article
            if not self.taux_gnr or self.taux_gnr == 0:
                self.taux_gnr = self.get_taux_gnr_article()
            
            # 2. Calculer le montant de taxe (quantité en L × taux en €/L)
            if self.quantite and self.taux_gnr:
                self.montant_taxe_gnr = flt(self.quantite * self.taux_gnr, 2)
                
        except Exception as e:
            frappe.log_error(f"Erreur calcul taux GNR pour {self.name}: {str(e)}")
    
    def get_taux_gnr_article(self):
        """Récupère le taux GNR depuis l'article"""
        if not self.code_produit:
            return 0
        
        try:
            # Récupérer depuis l'article
            taux_article = frappe.get_value("Item", self.code_produit, "gnr_tax_rate")
            
            if taux_article and taux_article > 0:
                return taux_article
            
            # Si pas de taux sur l'article, utiliser des taux par défaut selon la catégorie
            item_group = frappe.get_value("Item", self.code_produit, "item_group")
            
            default_rates = {
                "Combustibles/Carburants/GNR": 24.81,
                "Combustibles/Carburants/Gazole": 24.81,
                "Combustibles/Adblue": 0,
                "Combustibles/Fioul/Bio": 3.86,
                "Combustibles/Fioul/Hiver": 3.86,
                "Combustibles/Fioul/Standard": 3.86
            }
            
            return default_rates.get(item_group, 0)
            
        except Exception as e:
            frappe.log_error(f"Erreur récupération taux pour article {self.code_produit}: {str(e)}")
            return 0
    
    def calculer_periodes(self):
        """Calcule automatiquement trimestre, semestre et année"""
        if self.date_mouvement:
            date_obj = getdate(self.date_mouvement)
            
            self.annee = date_obj.year
            self.trimestre = str((date_obj.month - 1) // 3 + 1)
            self.semestre = "1" if date_obj.month <= 6 else "2"
    
    def before_save(self):
        """Actions avant sauvegarde"""
        self.calculer_taux_et_montants()
    
    @frappe.whitelist()
    def recalculer_taux_et_montants(self):
        """Méthode publique pour recalculer les taux et montants"""
        self.calculer_taux_et_montants()
        self.save()
        return {
            "taux_gnr": self.taux_gnr,
            "montant_taxe_gnr": self.montant_taxe_gnr,
            "message": "Calculs mis à jour"
        }