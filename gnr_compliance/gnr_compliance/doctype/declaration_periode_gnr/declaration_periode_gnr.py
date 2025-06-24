# gnr_compliance/gnr_compliance/doctype/declaration_periode_gnr/declaration_periode_gnr.py

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from gnr_compliance.utils.export_formats_exacts import generer_declaration_trimestrielle_exacte, generer_liste_semestrielle_exacte

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
            
        try:
            # Debug : vérifier s'il y a des mouvements
            count_mouvements = frappe.db.count("Mouvement GNR", {
                "date_mouvement": ["between", [self.date_debut, self.date_fin]],
                "docstatus": 1
            })
            
            frappe.logger().info(f"Debug Declaration GNR: {count_mouvements} mouvements trouvés entre {self.date_debut} et {self.date_fin}")
            
            # Calculer les totaux depuis les mouvements GNR avec info attestation basée sur les champs dossier
            totaux = frappe.db.sql("""
                SELECT 
                    SUM(CASE WHEN m.type_mouvement = 'Vente' THEN m.quantite ELSE 0 END) as total_ventes,
                    SUM(COALESCE(m.montant_taxe_gnr, 0)) as total_taxe_gnr,
                    COUNT(DISTINCT CASE WHEN m.client IS NOT NULL THEN m.client END) as nb_clients
                FROM `tabMouvement GNR` m
                LEFT JOIN `tabCustomer` c ON m.client = c.name
                WHERE m.date_mouvement BETWEEN %s AND %s
                AND m.docstatus = 1
            """, (self.date_debut, self.date_fin), as_dict=True)
            
            if totaux and len(totaux) > 0:
                self.total_ventes = totaux[0].total_ventes or 0
                self.total_taxe_gnr = totaux[0].total_taxe_gnr or 0
                self.nb_clients = totaux[0].nb_clients or 0
                
                frappe.logger().info(f"Debug Declaration GNR: Calculé - Ventes: {self.total_ventes}, Taxe: {self.total_taxe_gnr}, Clients: {self.nb_clients}")
            else:
                self.total_ventes = 0
                self.total_taxe_gnr = 0
                self.nb_clients = 0
                
        except Exception as e:
            frappe.log_error(f"Erreur calcul données période: {str(e)}")
            self.total_ventes = 0
            self.total_taxe_gnr = 0
            self.nb_clients = 0
    
    @frappe.whitelist()
    def calculer_donnees_forcees(self):
        """Force le calcul des données même sans changement"""
        try:
            # Calculer les données
            self.calculer_donnees_periode()
            
            # Sauvegarder les changements
            self.save(ignore_permissions=True)
            
            # Préparer le message de retour
            if self.total_ventes or self.total_taxe_gnr:
                message = f"✅ Données calculées : {self.total_ventes or 0}L vendus, {self.total_taxe_gnr or 0}€ de taxe, {self.nb_clients or 0} clients"
                return {
                    "success": True,
                    "message": message,
                    "data": {
                        "total_ventes": self.total_ventes,
                        "total_taxe_gnr": self.total_taxe_gnr,
                        "nb_clients": self.nb_clients
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "⚠️ Aucune donnée GNR trouvée pour cette période"
                }
                
        except Exception as e:
            frappe.log_error(f"Erreur calcul forcé: {str(e)}")
            return {
                "success": False,
                "message": f"Erreur lors du calcul : {str(e)}"
            }
    
    @frappe.whitelist()
    def diagnostiquer_donnees(self):
        """Diagnostic des données disponibles pour la période"""
        try:
            if not self.date_debut or not self.date_fin:
                return {"error": "Dates non définies"}
            
            # Compter les mouvements par type avec info attestation basée sur numéro dossier et date dépôt
            mouvements_stats = frappe.db.sql("""
                SELECT 
                    m.type_mouvement,
                    COUNT(*) as count,
                    SUM(m.quantite) as quantite,
                    SUM(COALESCE(m.montant_taxe_gnr, 0)) as taxe,
                    SUM(CASE WHEN m.type_mouvement = 'Vente' AND (c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL) THEN m.quantite ELSE 0 END) as quantite_avec_attestation,
                    SUM(CASE WHEN m.type_mouvement = 'Vente' AND (c.custom_n_dossier_ IS NULL OR c.custom_n_dossier_ = '' OR c.custom_date_de_depot IS NULL) THEN m.quantite ELSE 0 END) as quantite_sans_attestation
                FROM `tabMouvement GNR` m
                LEFT JOIN `tabCustomer` c ON m.client = c.name
                WHERE m.date_mouvement BETWEEN %s AND %s
                AND m.docstatus = 1
                GROUP BY m.type_mouvement
            """, (self.date_debut, self.date_fin), as_dict=True)
            
            # Calculer les totaux
            total_mouvements = sum([m.count for m in mouvements_stats])
            quantite_totale = sum([m.quantite or 0 for m in mouvements_stats])
            taxe_totale = sum([m.taxe or 0 for m in mouvements_stats])
            
            # Totaux avec/sans attestation
            total_avec_attestation = sum([m.quantite_avec_attestation or 0 for m in mouvements_stats])
            total_sans_attestation = sum([m.quantite_sans_attestation or 0 for m in mouvements_stats])
            
            # Compter les clients uniques avec distinction attestation basée sur les champs dossier
            clients_stats = frappe.db.sql("""
                SELECT 
                    COUNT(DISTINCT m.client) as count,
                    COUNT(DISTINCT CASE WHEN (c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL) THEN m.client END) as clients_avec_attestation,
                    COUNT(DISTINCT CASE WHEN (c.custom_n_dossier_ IS NULL OR c.custom_n_dossier_ = '' OR c.custom_date_de_depot IS NULL) THEN m.client END) as clients_sans_attestation
                FROM `tabMouvement GNR` m
                LEFT JOIN `tabCustomer` c ON m.client = c.name
                WHERE m.date_mouvement BETWEEN %s AND %s
                AND m.docstatus = 1
                AND m.client IS NOT NULL
            """, (self.date_debut, self.date_fin), as_dict=True)
            
            clients_data = clients_stats[0] if clients_stats else {}
            
            # Organiser par type
            stats_par_type = {}
            for stat in mouvements_stats:
                stats_par_type[stat.type_mouvement] = stat.count
            
            return {
                "total_mouvements": total_mouvements,
                "ventes": stats_par_type.get("Vente", 0),
                "achats": stats_par_type.get("Achat", 0),
                "autres": total_mouvements - stats_par_type.get("Vente", 0) - stats_par_type.get("Achat", 0),
                "quantite_totale": round(quantite_totale, 2),
                "taxe_totale": round(taxe_totale, 2),
                "clients_uniques": clients_data.get("count", 0),
                "clients_avec_attestation": clients_data.get("clients_avec_attestation", 0),
                "clients_sans_attestation": clients_data.get("clients_sans_attestation", 0),
                "volume_avec_attestation": round(total_avec_attestation, 2),
                "volume_sans_attestation": round(total_sans_attestation, 2),
                "periode": f"{self.date_debut} au {self.date_fin}"
            }
            
        except Exception as e:
            frappe.log_error(f"Erreur diagnostic données: {str(e)}")
            return {"error": str(e)}

    @frappe.whitelist()
    def generer_export_reglementaire(self, format_export="xlsx"):
        """Génère l'export selon le type de période et format EXACT"""
        
        try:
            if self.type_periode == "Trimestriel":
                # Générer la Déclaration Trimestrielle au format exact
                return generer_declaration_trimestrielle_exacte(self.date_debut, self.date_fin)
                
            elif self.type_periode == "Semestriel":
                # Générer la Liste Semestrielle des Clients au format exact
                return generer_liste_semestrielle_exacte(self.date_debut, self.date_fin)
                
            elif self.type_periode == "Annuel":
                # Pour l'annuel, on génère les deux types de documents
                try:
                    # Générer la déclaration trimestrielle pour l'année
                    arrete = generer_declaration_trimestrielle_exacte(self.date_debut, self.date_fin)
                    
                    # Générer la liste clients pour l'année
                    liste_clients = generer_liste_semestrielle_exacte(self.date_debut, self.date_fin)
                    
                    # Vérifier si au moins un des deux a réussi
                    if arrete and arrete.get("success"):
                        if liste_clients and liste_clients.get("success"):
                            # Les deux ont réussi
                            return {
                                "success": True,
                                "arrete_url": arrete["file_url"],
                                "clients_url": liste_clients["file_url"],
                                "message": "Déclaration annuelle et liste clients générées"
                            }
                        else:
                            # Seule la déclaration a réussi
                            return {
                                "success": True,
                                "file_url": arrete["file_url"],
                                "file_name": arrete["file_name"],
                                "message": "Déclaration annuelle générée (liste clients échouée)"
                            }
                    elif liste_clients and liste_clients.get("success"):
                        # Seule la liste clients a réussi
                        return {
                            "success": True,
                            "file_url": liste_clients["file_url"],
                            "file_name": liste_clients["file_name"],
                            "message": "Liste clients annuelle générée (déclaration échouée)"
                        }
                    else:
                        # Les deux ont échoué
                        return {
                            "success": False,
                            "message": "Échec de la génération des exports annuels"
                        }
                        
                except Exception as e:
                    frappe.log_error(f"Erreur export annuel: {str(e)}")
                    return {
                        "success": False,
                        "message": f"Erreur lors de la génération annuelle: {str(e)}"
                    }
            
            else:
                return {
                    "success": False,
                    "message": "Type de période non supporté pour l'export"
                }
                
        except Exception as e:
            frappe.log_error(f"Erreur export réglementaire: {str(e)}")
            return {
                "success": False,
                "message": f"Erreur: {str(e)}"
            }
    
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