# gnr_compliance/gnr_compliance/doctype/declaration_periode_gnr/declaration_periode_gnr.py

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from gnr_compliance.utils.export_reglementaire import generer_arrete_trimestriel, generer_liste_semestrielle_clients

class DeclarationPeriodeGNR(Document):
    def validate(self):
        """Validation avant sauvegarde"""
        self.calculer_dates_automatiques()
        self.calculer_donnees_periode()
        
    def calculer_dates_automatiques(self):
        """Calcule automatiquement les dates selon la période"""
        if not self.annee or not self.periode:
            return
            
        if self.type_periode == "Trimestriel":
            trimestre = int(self.periode[1])  # T1 -> 1
            mois_debut = (trimestre - 1) * 3 + 1
            mois_fin = trimestre * 3
            
            self.date_debut = f"{self.annee}-{mois_debut:02d}-01"
            # Dernier jour du mois
            import calendar
            dernier_jour = calendar.monthrange(self.annee, mois_fin)[1]
            self.date_fin = f"{self.annee}-{mois_fin:02d}-{dernier_jour}"
            
        elif self.type_periode == "Semestriel":
            semestre = int(self.periode[1])  # S1 -> 1
            if semestre == 1:
                self.date_debut = f"{self.annee}-01-01"
                self.date_fin = f"{self.annee}-06-30"
            else:
                self.date_debut = f"{self.annee}-07-01"
                self.date_fin = f"{self.annee}-12-31"
                
        elif self.type_periode == "Annuel":
            self.date_debut = f"{self.annee}-01-01"
            self.date_fin = f"{self.annee}-12-31"
    
    def calculer_donnees_periode(self):
        """Calcule les données de la période"""
        if not self.date_debut or not self.date_fin:
            return
            
        # Calculer les totaux depuis les mouvements GNR
        totaux = frappe.db.sql("""
            SELECT 
                SUM(CASE WHEN type_mouvement = 'Vente' THEN quantite ELSE 0 END) as total_ventes,
                SUM(montant_taxe_gnr) as total_taxe_gnr,
                COUNT(DISTINCT client) as nb_clients
            FROM `tabMouvement GNR`
            WHERE date_mouvement BETWEEN %s AND %s
            AND docstatus = 1
        """, (self.date_debut, self.date_fin), as_dict=True)
        
        if totaux:
            self.total_ventes = totaux[0].total_ventes or 0
            self.total_taxe_gnr = totaux[0].total_taxe_gnr or 0
            self.nb_clients = totaux[0].nb_clients or 0
    
    @frappe.whitelist()
    def generer_export_reglementaire(self):
        """Génère l'export selon le type de période"""
        
        if self.type_periode == "Trimestriel":
            # Générer l'Arrêté Trimestriel de Stock Détaillé
            return generer_arrete_trimestriel(self.date_debut, self.date_fin, True)
            
        elif self.type_periode == "Semestriel":
            # Générer la Liste Semestrielle des Clients
            if not self.inclure_details_clients:
                frappe.throw("La liste des clients est obligatoire pour les déclarations semestrielles")
            
            return generer_liste_semestrielle_clients(self.date_debut, self.date_fin)
            
        elif self.type_periode == "Annuel":
            # Pour l'annuel, on peut générer les deux
            arrete = generer_arrete_trimestriel(self.date_debut, self.date_fin, True)
            liste_clients = generer_liste_semestrielle_clients(self.date_debut, self.date_fin)
            
            return {
                "arrete_url": arrete["file_url"],
                "clients_url": liste_clients["file_url"],
                "message": "Deux fichiers générés : Arrêté annuel et Liste clients"
            }
        
        else:
            frappe.throw("Type de période non supporté pour l'export")
    
    def before_submit(self):
        """Validations avant soumission"""
        if self.type_periode == "Semestriel" and not self.inclure_details_clients:
            frappe.throw("Les détails clients sont obligatoires pour les déclarations semestrielles")
        
        # Vérifier qu'il y a des données
        if not self.total_ventes and not self.total_taxe_gnr:
            frappe.msgprint("Aucune donnée GNR trouvée pour cette période", alert=True)
        
        self.statut = "Soumise"
    
    def on_submit(self):
        """Actions après soumission"""
        self.statut = "Validée"
    
    def on_cancel(self):
        """Actions après annulation"""
        self.statut = "Annulée"