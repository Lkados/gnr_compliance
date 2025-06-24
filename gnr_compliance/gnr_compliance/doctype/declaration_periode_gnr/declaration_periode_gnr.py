# gnr_compliance/gnr_compliance/doctype/declaration_periode_gnr/declaration_periode_gnr.py

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from gnr_compliance.utils.export_formats_exacts import generer_declaration_trimestrielle_exacte, generer_liste_semestrielle_exacte

class DeclarationPeriodeGNR(Document):
    def validate(self):
        """Validation avant sauvegarde AVEC CALCULS RÉELS"""
        self.calculer_dates_automatiques()
        self.calculer_donnees_periode_reelles()
        
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
    
    def calculer_donnees_periode_reelles(self):
        """
        Calcule les données de la période AVEC LES VRAIS MONTANTS
        Récupère les montants de taxe et prix réellement facturés
        """
        if not self.date_debut or not self.date_fin:
            return
            
        try:
            # Debug : vérifier s'il y a des mouvements
            count_mouvements = frappe.db.count("Mouvement GNR", {
                "date_mouvement": ["between", [self.date_debut, self.date_fin]],
                "docstatus": 1
            })
            
            frappe.logger().info(f"Debug Declaration GNR: {count_mouvements} mouvements trouvés entre {self.date_debut} et {self.date_fin}")
            
            # Calculer les totaux RÉELS depuis les mouvements GNR avec info attestation
            totaux = frappe.db.sql("""
                SELECT 
                    SUM(CASE WHEN m.type_mouvement = 'Vente' THEN m.quantite ELSE 0 END) as total_ventes,
                    SUM(CASE WHEN m.type_mouvement IN ('Achat', 'Entrée') THEN m.quantite ELSE 0 END) as total_entrees,
                    SUM(CASE WHEN m.type_mouvement IN ('Vente', 'Sortie') THEN m.quantite ELSE 0 END) as total_sorties,
                    -- UTILISER LES VRAIS MONTANTS DE TAXE ENREGISTRÉS
                    SUM(COALESCE(m.montant_taxe_gnr, 0)) as total_taxe_gnr_reel,
                    -- CALCULER LE CHIFFRE D'AFFAIRES RÉEL
                    SUM(CASE WHEN m.type_mouvement = 'Vente' THEN COALESCE(m.quantite * m.prix_unitaire, 0) ELSE 0 END) as ca_reel,
                    -- CALCULER LES TAUX MOYENS RÉELS
                    CASE 
                        WHEN SUM(CASE WHEN m.type_mouvement = 'Vente' THEN m.quantite ELSE 0 END) > 0
                        THEN SUM(COALESCE(m.montant_taxe_gnr, 0)) / SUM(CASE WHEN m.type_mouvement = 'Vente' THEN m.quantite ELSE 0 END)
                        ELSE 0
                    END as taux_moyen_reel,
                    COUNT(DISTINCT CASE WHEN m.client IS NOT NULL THEN m.client END) as nb_clients,
                    -- STATISTIQUES PAR TYPE D'ATTESTATION (CHAMPS RÉELS DU CLIENT)
                    SUM(CASE 
                        WHEN m.type_mouvement = 'Vente' 
                        AND c.custom_n_dossier_ IS NOT NULL 
                        AND c.custom_n_dossier_ != '' 
                        AND c.custom_date_de_depot IS NOT NULL 
                        THEN m.quantite 
                        ELSE 0 
                    END) as volume_avec_attestation_reel,
                    SUM(CASE 
                        WHEN m.type_mouvement = 'Vente' 
                        AND (c.custom_n_dossier_ IS NULL OR c.custom_n_dossier_ = '' OR c.custom_date_de_depot IS NULL)
                        THEN m.quantite 
                        ELSE 0 
                    END) as volume_sans_attestation_reel,
                    -- MONTANTS DE TAXE PAR TYPE D'ATTESTATION
                    SUM(CASE 
                        WHEN m.type_mouvement = 'Vente' 
                        AND c.custom_n_dossier_ IS NOT NULL 
                        AND c.custom_n_dossier_ != '' 
                        AND c.custom_date_de_depot IS NOT NULL 
                        THEN COALESCE(m.montant_taxe_gnr, 0)
                        ELSE 0 
                    END) as taxe_avec_attestation_reel,
                    SUM(CASE 
                        WHEN m.type_mouvement = 'Vente' 
                        AND (c.custom_n_dossier_ IS NULL OR c.custom_n_dossier_ = '' OR c.custom_date_de_depot IS NULL)
                        THEN COALESCE(m.montant_taxe_gnr, 0)
                        ELSE 0 
                    END) as taxe_sans_attestation_reel
                FROM `tabMouvement GNR` m
                LEFT JOIN `tabCustomer` c ON m.client = c.name
                WHERE m.date_mouvement BETWEEN %s AND %s
                AND m.docstatus = 1
            """, (self.date_debut, self.date_fin), as_dict=True)
            
            if totaux and len(totaux) > 0:
                result = totaux[0]
                self.total_ventes = result.total_ventes or 0
                self.total_taxe_gnr = result.total_taxe_gnr_reel or 0  # VRAI MONTANT TAXE
                self.nb_clients = result.nb_clients or 0
                
                # Ajouter les nouvelles métriques si les champs existent
                try:
                    self.total_entrees = result.total_entrees or 0
                    self.total_sorties = result.total_sorties or 0
                    self.ca_reel = result.ca_reel or 0
                    self.taux_moyen_reel = result.taux_moyen_reel or 0
                    self.volume_avec_attestation = result.volume_avec_attestation_reel or 0
                    self.volume_sans_attestation = result.volume_sans_attestation_reel or 0
                    self.taxe_avec_attestation = result.taxe_avec_attestation_reel or 0
                    self.taxe_sans_attestation = result.taxe_sans_attestation_reel or 0
                except AttributeError:
                    # Les champs n'existent pas encore, les ignorer
                    pass
                
                frappe.logger().info(f"Debug Declaration GNR: Calculé - Ventes: {self.total_ventes}, Taxe RÉELLE: {self.total_taxe_gnr}, Clients: {self.nb_clients}")
            else:
                self.total_ventes = 0
                self.total_taxe_gnr = 0
                self.nb_clients = 0
                
        except Exception as e:
            frappe.log_error(f"Erreur calcul données période avec vrais montants: {str(e)}")
            self.total_ventes = 0
            self.total_taxe_gnr = 0
            self.nb_clients = 0
    
    @frappe.whitelist()
    def calculer_donnees_forcees(self):
        """Force le calcul des données même sans changement AVEC VRAIS MONTANTS"""
        try:
            # Calculer les données réelles
            self.calculer_donnees_periode_reelles()
            
            # Sauvegarder les changements
            self.save(ignore_permissions=True)
            
            # Préparer le message de retour avec détails réels
            if self.total_ventes or self.total_taxe_gnr:
                # Calculer des statistiques additionnelles
                taux_moyen = self.total_taxe_gnr / self.total_ventes if self.total_ventes > 0 else 0
                
                message = f"✅ Données RÉELLES calculées : {self.total_ventes or 0}L vendus, {self.total_taxe_gnr or 0}€ de taxe réelle, {self.nb_clients or 0} clients (Taux moyen: {taux_moyen:.3f}€/L)"
                return {
                    "success": True,
                    "message": message,
                    "data": {
                        "total_ventes": self.total_ventes,
                        "total_taxe_gnr_reel": self.total_taxe_gnr,
                        "nb_clients": self.nb_clients,
                        "taux_moyen_reel": taux_moyen,
                        "ca_reel": getattr(self, 'ca_reel', 0),
                        "volume_avec_attestation": getattr(self, 'volume_avec_attestation', 0),
                        "volume_sans_attestation": getattr(self, 'volume_sans_attestation', 0)
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "⚠️ Aucune donnée GNR trouvée pour cette période"
                }
                
        except Exception as e:
            frappe.log_error(f"Erreur calcul forcé avec vrais montants: {str(e)}")
            return {
                "success": False,
                "message": f"Erreur lors du calcul : {str(e)}"
            }
    
    @frappe.whitelist()
    def diagnostiquer_donnees(self):
        """Diagnostic des données disponibles avec VRAIS MONTANTS ET TAUX"""
        try:
            if not self.date_debut or not self.date_fin:
                return {"error": "Dates non définies"}
            
            # Compter les mouvements par type avec VRAIS MONTANTS
            mouvements_stats = frappe.db.sql("""
                SELECT 
                    m.type_mouvement,
                    COUNT(*) as count,
                    SUM(m.quantite) as quantite,
                    -- UTILISER LES VRAIS MONTANTS DE TAXE
                    SUM(COALESCE(m.montant_taxe_gnr, 0)) as taxe_reelle,
                    -- CALCULER LES VRAIS CHIFFRES D'AFFAIRES
                    SUM(COALESCE(m.quantite * m.prix_unitaire, 0)) as ca_reel,
                    -- VOLUMES PAR TYPE D'ATTESTATION (CHAMPS RÉELS)
                    SUM(CASE 
                        WHEN m.type_mouvement = 'Vente' 
                        AND (c.custom_n_dossier_ IS NOT NULL AND c.custom_n_dossier_ != '' AND c.custom_date_de_depot IS NOT NULL) 
                        THEN m.quantite 
                        ELSE 0 
                    END) as quantite_avec_attestation,
                    SUM(CASE 
                        WHEN m.type_mouvement = 'Vente' 
                        AND (c.custom_n_dossier_ IS NULL OR c.custom_n_dossier_ = '' OR c.custom_date_de_depot IS NULL) 
                        THEN m.quantite 
                        ELSE 0 
                    END) as quantite_sans_attestation,
                    -- TAUX MOYENS RÉELS
                    CASE 
                        WHEN SUM(m.quantite) > 0 
                        THEN SUM(COALESCE(m.montant_taxe_gnr, 0)) / SUM(m.quantite)
                        ELSE 0
                    END as taux_moyen_reel,
                    -- STATISTIQUES SUR LES TAUX
                    MIN(m.taux_gnr) as taux_min,
                    MAX(m.taux_gnr) as taux_max,
                    COUNT(CASE WHEN m.taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as nb_taux_suspects,
                    COUNT(CASE WHEN m.taux_gnr = 0 THEN 1 END) as nb_taux_zero
                FROM `tabMouvement GNR` m
                LEFT JOIN `tabCustomer` c ON m.client = c.name
                WHERE m.date_mouvement BETWEEN %s AND %s
                AND m.docstatus = 1
                GROUP BY m.type_mouvement
            """, (self.date_debut, self.date_fin), as_dict=True)
            
            # Calculer les totaux
            total_mouvements = sum([m.count for m in mouvements_stats])
            quantite_totale = sum([m.quantite or 0 for m in mouvements_stats])
            taxe_totale_reelle = sum([m.taxe_reelle or 0 for m in mouvements_stats])
            ca_total_reel = sum([m.ca_reel or 0 for m in mouvements_stats])
            
            # Totaux avec/sans attestation
            total_avec_attestation = sum([m.quantite_avec_attestation or 0 for m in mouvements_stats])
            total_sans_attestation = sum([m.quantite_sans_attestation or 0 for m in mouvements_stats])
            
            # Taux moyen réel global
            taux_moyen_global = taxe_totale_reelle / quantite_totale if quantite_totale > 0 else 0
            
            # Statistiques sur les taux
            total_taux_suspects = sum([m.nb_taux_suspects or 0 for m in mouvements_stats])
            total_taux_zero = sum([m.nb_taux_zero or 0 for m in mouvements_stats])
            
            # Compter les clients uniques avec distinction attestation
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
            
            # Organiser par type avec détails des taux
            stats_par_type = {}
            for stat in mouvements_stats:
                stats_par_type[stat.type_mouvement] = {
                    'count': stat.count,
                    'taux_moyen_reel': stat.taux_moyen_reel,
                    'taux_min': stat.taux_min,
                    'taux_max': stat.taux_max,
                    'nb_taux_suspects': stat.nb_taux_suspects,
                    'nb_taux_zero': stat.nb_taux_zero
                }
            
            # Indicateurs de qualité des données
            qualite_donnees = {
                'pourcentage_taux_suspects': (total_taux_suspects / total_mouvements * 100) if total_mouvements > 0 else 0,
                'pourcentage_taux_zero': (total_taux_zero / total_mouvements * 100) if total_mouvements > 0 else 0,
                'coherence_ok': total_taux_suspects == 0 and total_taux_zero == 0
            }
            
            return {
                "total_mouvements": total_mouvements,
                "ventes": stats_par_type.get("Vente", {}).get('count', 0),
                "achats": stats_par_type.get("Achat", {}).get('count', 0),
                "autres": total_mouvements - stats_par_type.get("Vente", {}).get('count', 0) - stats_par_type.get("Achat", {}).get('count', 0),
                "quantite_totale": round(quantite_totale, 2),
                "taxe_totale_reelle": round(taxe_totale_reelle, 2),  # VRAIE TAXE
                "ca_total_reel": round(ca_total_reel, 2),  # VRAI CA
                "taux_moyen_global_reel": round(taux_moyen_global, 4),  # VRAI TAUX MOYEN
                "clients_uniques": clients_data.get("count", 0),
                "clients_avec_attestation": clients_data.get("clients_avec_attestation", 0),
                "clients_sans_attestation": clients_data.get("clients_sans_attestation", 0),
                "volume_avec_attestation": round(total_avec_attestation, 2),
                "volume_sans_attestation": round(total_sans_attestation, 2),
                "taux_vente_reel": round(stats_par_type.get("Vente", {}).get('taux_moyen_reel', 0), 4),
                "stats_par_type": stats_par_type,
                "qualite_donnees": qualite_donnees,
                "total_taux_suspects": total_taux_suspects,
                "total_taux_zero": total_taux_zero,
                "periode": f"{self.date_debut} au {self.date_fin}"
            }
            
        except Exception as e:
            frappe.log_error(f"Erreur diagnostic données avec vrais montants: {str(e)}")
            return {"error": str(e)}

    @frappe.whitelist()
    def generer_export_reglementaire(self, format_export="xlsx"):
        """Génère l'export selon le type de période et format EXACT AVEC VRAIS TAUX"""
        
        try:
            if self.type_periode == "Trimestriel":
                # Générer la Déclaration Trimestrielle au format exact avec vrais taux
                return generer_declaration_trimestrielle_exacte(self.date_debut, self.date_fin)
                
            elif self.type_periode == "Semestriel":
                # Générer la Liste Semestrielle des Clients au format exact avec vrais tarifs
                return generer_liste_semestrielle_exacte(self.date_debut, self.date_fin)
                
            elif self.type_periode == "Annuel":
                # Pour l'annuel, on génère les deux types de documents avec vrais montants
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
                                "message": "Déclaration annuelle et liste clients générées avec taux réels"
                            }
                        else:
                            # Seule la déclaration a réussi
                            return {
                                "success": True,
                                "file_url": arrete["file_url"],
                                "file_name": arrete["file_name"],
                                "message": "Déclaration annuelle générée avec taux réels (liste clients échouée)"
                            }
                    elif liste_clients and liste_clients.get("success"):
                        # Seule la liste clients a réussi
                        return {
                            "success": True,
                            "file_url": liste_clients["file_url"],
                            "file_name": liste_clients["file_name"],
                            "message": "Liste clients annuelle générée avec tarifs réels (déclaration échouée)"
                        }
                    else:
                        # Les deux ont échoué
                        return {
                            "success": False,
                            "message": "Échec de la génération des exports annuels avec taux réels"
                        }
                        
                except Exception as e:
                    frappe.log_error(f"Erreur export annuel avec vrais taux: {str(e)}")
                    return {
                        "success": False,
                        "message": f"Erreur lors de la génération annuelle avec taux réels: {str(e)}"
                    }
            
            else:
                return {
                    "success": False,
                    "message": "Type de période non supporté pour l'export"
                }
                
        except Exception as e:
            frappe.log_error(f"Erreur export réglementaire avec vrais taux: {str(e)}")
            return {
                "success": False,
                "message": f"Erreur: {str(e)}"
            }
    
    @frappe.whitelist()
    def valider_coherence_donnees(self):
        """
        Valide la cohérence des données GNR pour cette déclaration
        Vérifie que les taux sont réels et non des valeurs par défaut
        """
        try:
            if not self.date_debut or not self.date_fin:
                return {"success": False, "message": "Dates de période manquantes"}
            
            # Analyser la qualité des données
            analyse = frappe.db.sql("""
                SELECT 
                    COUNT(*) as total_mouvements,
                    COUNT(CASE WHEN taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as taux_suspects,
                    COUNT(CASE WHEN taux_gnr = 0 THEN 1 END) as taux_zero,
                    COUNT(CASE WHEN taux_gnr < 0.1 OR taux_gnr > 50 THEN 1 END) as taux_aberrants,
                    COUNT(CASE WHEN montant_taxe_gnr != (quantite * taux_gnr) THEN 1 END) as calculs_incorrects,
                    AVG(taux_gnr) as taux_moyen,
                    MIN(taux_gnr) as taux_min,
                    MAX(taux_gnr) as taux_max
                FROM `tabMouvement GNR`
                WHERE date_mouvement BETWEEN %s AND %s
                AND docstatus = 1
                AND quantite > 0
            """, (self.date_debut, self.date_fin), as_dict=True)
            
            if not analyse:
                return {"success": False, "message": "Aucun mouvement GNR trouvé"}
            
            stats = analyse[0]
            
            # Calculer les pourcentages
            total = stats.total_mouvements
            if total == 0:
                return {"success": False, "message": "Aucun mouvement GNR valide trouvé"}
            
            pourcentage_suspects = (stats.taux_suspects / total) * 100
            pourcentage_zero = (stats.taux_zero / total) * 100
            pourcentage_aberrants = (stats.taux_aberrants / total) * 100
            pourcentage_calculs_incorrects = (stats.calculs_incorrects / total) * 100
            
            # Déterminer le niveau de qualité
            if pourcentage_suspects == 0 and pourcentage_aberrants == 0 and pourcentage_calculs_incorrects == 0:
                niveau_qualite = "EXCELLENT"
                couleur = "green"
            elif pourcentage_suspects < 10 and pourcentage_aberrants < 5:
                niveau_qualite = "BON"
                couleur = "orange"
            else:
                niveau_qualite = "PROBLÉMATIQUE"
                couleur = "red"
            
            # Générer des recommandations
            recommandations = []
            if stats.taux_suspects > 0:
                recommandations.append(f"⚠️ {stats.taux_suspects} mouvements utilisent des taux par défaut suspects")
            if stats.taux_zero > 0:
                recommandations.append(f"ℹ️ {stats.taux_zero} mouvements ont un taux zéro (vérifiez si normal)")
            if stats.taux_aberrants > 0:
                recommandations.append(f"❌ {stats.taux_aberrants} mouvements ont des taux aberrants")
            if stats.calculs_incorrects > 0:
                recommandations.append(f"🔢 {stats.calculs_incorrects} mouvements ont des erreurs de calcul")
            
            if not recommandations:
                recommandations.append("✅ Toutes les données semblent cohérentes")
            
            return {
                "success": True,
                "niveau_qualite": niveau_qualite,
                "couleur": couleur,
                "statistiques": {
                    "total_mouvements": total,
                    "taux_suspects": stats.taux_suspects,
                    "taux_zero": stats.taux_zero,
                    "taux_aberrants": stats.taux_aberrants,
                    "calculs_incorrects": stats.calculs_incorrects,
                    "pourcentage_suspects": round(pourcentage_suspects, 1),
                    "pourcentage_zero": round(pourcentage_zero, 1),
                    "pourcentage_aberrants": round(pourcentage_aberrants, 1),
                    "pourcentage_calculs_incorrects": round(pourcentage_calculs_incorrects, 1),
                    "taux_moyen": round(stats.taux_moyen, 3),
                    "taux_min": stats.taux_min,
                    "taux_max": stats.taux_max
                },
                "recommandations": recommandations
            }
            
        except Exception as e:
            frappe.log_error(f"Erreur validation cohérence: {str(e)}")
            return {"success": False, "message": f"Erreur: {str(e)}"}
    
    def before_submit(self):
        """Validations avant soumission AVEC VÉRIFICATION DES VRAIS TAUX"""
        if self.type_periode == "Semestriel" and not self.inclure_details_clients:
            frappe.throw("Les détails clients sont obligatoires pour les déclarations semestrielles")
        
        # Vérifier qu'il y a des données
        if not self.total_ventes and not self.total_taxe_gnr:
            frappe.msgprint("Aucune donnée GNR trouvée pour cette période", alert=True)
        
        # Valider la cohérence des taux avant soumission
        validation = self.valider_coherence_donnees()
        if validation.get("success") and validation.get("niveau_qualite") == "PROBLÉMATIQUE":
            frappe.msgprint({
                "title": "⚠️ Données problématiques détectées",
                "message": f"Niveau de qualité: {validation['niveau_qualite']}<br>" + 
                          "<br>".join(validation.get("recommandations", [])),
                "indicator": "orange"
            })
        
        self.statut = "Soumise"
    
    def on_submit(self):
        """Actions après soumission"""
        self.statut = "Validée"
    
    def on_cancel(self):
        """Actions après annulation"""
        self.statut = "Annulée"