# Copyright (c) 2025, Mohamed Kachtit and contributors
# For license information, please see license.txt

from frappe.model.document import Document

class MouvementGNR(Document):
    def validate(self):
        """Calcul automatique lors de la validation"""
        self.calculer_montant_taxe()
    
    def calculer_montant_taxe(self):
        """Calcule le montant de taxe GNR"""
        if self.quantite and self.taux_gnr:
            self.montant_taxe_gnr = self.quantite * self.taux_gnr