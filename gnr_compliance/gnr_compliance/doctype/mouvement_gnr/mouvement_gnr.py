# Copyright (c) 2025, Mohamed Kachtit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate
import re

class MouvementGNR(Document):
    def validate(self):
        """Validation avec calculs automatiques UTILISANT LES VRAIS TAUX"""
        self.calculer_taux_et_montants()
        self.calculer_periodes()
    
    def calculer_taux_et_montants(self):
        """
        Calcule automatiquement le taux GNR et le montant de taxe
        AVEC RÉCUPÉRATION DES VRAIS TAUX DEPUIS TOUTES LES SOURCES
        """
        try:
            # 1. Si pas de taux GNR, essayer de le récupérer depuis toutes les sources possibles
            if not self.taux_gnr or self.taux_gnr == 0:
                self.taux_gnr = self.get_real_taux_gnr_from_all_sources()
            
            # 2. Calculer le montant de taxe (quantité en L × taux en €/L)
            if self.quantite and self.taux_gnr:
                self.montant_taxe_gnr = flt(self.quantite * self.taux_gnr, 2)
                
        except Exception as e:
            frappe.log_error(f"Erreur calcul taux GNR réels pour {self.name}: {str(e)}")
    
    def get_real_taux_gnr_from_all_sources(self):
        """
        RÉCUPÈRE LE TAUX GNR DEPUIS TOUTES LES SOURCES POSSIBLES
        
        PRIORITÉS:
        1. Document de référence (facture) - VRAIS TAUX
        2. Taux défini sur l'article
        3. Historique des mouvements de cet article
        4. Analyse du nom de l'article
        5. Taux par défaut selon la catégorie (DERNIER RECOURS)
        """
        if not self.code_produit:
            return 0
        
        try:
            # 1. PRIORITÉ 1: Si on a une référence de document (facture), récupérer depuis celle-ci
            if self.reference_document and self.reference_name:
                if self.reference_document in ["Sales Invoice", "Purchase Invoice"]:
                    doc_rate = self.get_taux_from_reference_document()
                    if doc_rate and 0.1 <= doc_rate <= 50:
                        frappe.logger().info(f"[GNR] Taux RÉEL depuis document {self.reference_name}: {doc_rate}€/L")
                        return doc_rate
            
            # 2. PRIORITÉ 2: Taux défini sur l'article maître
            taux_article = frappe.get_value("Item", self.code_produit, "gnr_tax_rate")
            if taux_article and taux_article > 0:
                frappe.logger().info(f"[GNR] Taux depuis article maître: {taux_article}€/L")
                return taux_article
            
            # 3. PRIORITÉ 3: Historique des mouvements de cet article
            historical_rate = self.get_historical_rate_for_item()
            if historical_rate:
                frappe.logger().info(f"[GNR] Taux historique: {historical_rate}€/L")
                return historical_rate
            
            # 4. PRIORITÉ 4: Analyser le nom de l'article pour détecter la catégorie
            item_name = frappe.get_value("Item", self.code_produit, "item_name")
            category = self.detect_gnr_category_from_item(item_name)
            
            # 5. PRIORITÉ 5: Chercher dans les factures récentes contenant cet article
            recent_rate = self.get_recent_invoice_rate_for_item()
            if recent_rate:
                frappe.logger().info(f"[GNR] Taux depuis factures récentes: {recent_rate}€/L")
                return recent_rate
            
            # 6. DERNIER RECOURS: Taux par défaut selon la catégorie
            default_rate = self.get_default_rate_by_category(category)
            frappe.logger().warning(f"[GNR] Taux par défaut utilisé pour {self.code_produit} ({category}): {default_rate}€/L")
            return default_rate
            
        except Exception as e:
            frappe.log_error(f"Erreur récupération taux depuis toutes sources pour article {self.code_produit}: {str(e)}")
            return 0
    
    def get_taux_from_reference_document(self):
        """
        RÉCUPÈRE LE TAUX DEPUIS LE DOCUMENT DE RÉFÉRENCE (FACTURE)
        """
        try:
            if not self.reference_document or not self.reference_name:
                return 0
            
            # Récupérer le document source
            source_doc = frappe.get_doc(self.reference_document, self.reference_name)
            
            # Trouver l'item correspondant dans la facture
            for item in source_doc.items:
                if item.item_code == self.code_produit:
                    # Utiliser la fonction d'extraction des taux réels
                    return self.get_real_gnr_tax_from_invoice_item(item, source_doc)
            
            return 0
            
        except Exception as e:
            frappe.log_error(f"Erreur récupération taux depuis document référence: {str(e)}")
            return 0
    
    def get_real_gnr_tax_from_invoice_item(self, item, invoice_doc):
        """
        EXTRAIT LE VRAI TAUX GNR DEPUIS UNE LIGNE DE FACTURE
        """
        try:
            from gnr_compliance.utils.unit_conversions import convert_to_litres, get_item_unit
            
            # 1. Chercher dans les taxes de la facture
            if hasattr(invoice_doc, 'taxes') and invoice_doc.taxes:
                for tax_row in invoice_doc.taxes:
                    if tax_row.description:
                        description_lower = tax_row.description.lower()
                        gnr_keywords = ['gnr', 'accise', 'ticpe', 'gazole', 'fioul', 'carburant', 'tipp']
                        
                        if any(keyword in description_lower for keyword in gnr_keywords):
                            if item.qty > 0 and tax_row.tax_amount:
                                # Convertir en litres
                                item_unit = item.uom or get_item_unit(item.item_code)
                                quantity_in_litres = convert_to_litres(item.qty, item_unit)
                                
                                if quantity_in_litres > 0:
                                    taux_calcule = abs(tax_row.tax_amount) / quantity_in_litres
                                    if 0.1 <= taux_calcule <= 50:
                                        return taux_calcule
            
            # 2. Chercher dans un champ personnalisé de l'item
            if hasattr(item, 'gnr_tax_rate') and item.gnr_tax_rate:
                if 0.1 <= item.gnr_tax_rate <= 50:
                    return item.gnr_tax_rate
            
            # 3. Analyser les termes de la facture
            if hasattr(invoice_doc, 'terms') and invoice_doc.terms:
                patterns = [
                    r'(\d+[.,]\d+)\s*[€]\s*[/]\s*[Ll]',  # "3.86€/L"
                    r'taxe[:\s]+(\d+[.,]\d+)',            # "taxe: 3.86"
                    r'tipp[:\s]+(\d+[.,]\d+)',            # "tipp: 3.86"
                    r'accise[:\s]+(\d+[.,]\d+)',          # "accise: 3.86"
                    r'gnr[:\s]+(\d+[.,]\d+)'              # "gnr: 3.86"
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, invoice_doc.terms, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            taux_potentiel = float(match.replace(',', '.'))
                            if 0.1 <= taux_potentiel <= 50:
                                return taux_potentiel
            
            return 0
            
        except Exception as e:
            frappe.log_error(f"Erreur extraction taux depuis item facture: {str(e)}")
            return 0
    
    def get_historical_rate_for_item(self):
        """Récupère le taux historique le plus récent pour cet article"""
        try:
            result = frappe.db.sql("""
                SELECT taux_gnr 
                FROM `tabMouvement GNR` 
                WHERE code_produit = %s 
                AND taux_gnr IS NOT NULL 
                AND taux_gnr > 0.1
                AND taux_gnr < 50
                AND docstatus = 1
                AND name != %s
                ORDER BY date_mouvement DESC, creation DESC
                LIMIT 1
            """, (self.code_produit, self.name or ''))
            
            return result[0][0] if result else None
        except:
            return None
    
    def get_recent_invoice_rate_for_item(self):
        """Récupère le taux depuis les factures récentes de cet article"""
        try:
            result = frappe.db.sql("""
                SELECT m.taux_gnr
                FROM `tabMouvement GNR` m
                WHERE m.code_produit = %s
                AND m.reference_document IN ('Purchase Invoice', 'Sales Invoice')
                AND m.taux_gnr IS NOT NULL
                AND m.taux_gnr > 0.1
                AND m.taux_gnr < 50
                AND m.docstatus = 1
                AND m.name != %s
                AND m.date_mouvement >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
                ORDER BY m.date_mouvement DESC
                LIMIT 1
            """, (self.code_produit, self.name or ''))
            
            return result[0][0] if result else None
        except:
            return None
    
    def detect_gnr_category_from_item(self, item_name=""):
        """Détecte la catégorie GNR depuis le code/nom d'article"""
        text = f"{self.code_produit} {item_name or ''}".upper()
        
        if "ADBLUE" in text or "AD BLUE" in text or "AD-BLUE" in text:
            return "ADBLUE"
        elif "FIOUL" in text or "FUEL" in text:
            if "BIO" in text:
                return "FIOUL_BIO"
            elif "HIVER" in text or "WINTER" in text:
                return "FIOUL_HIVER"
            else:
                return "FIOUL_STANDARD"
        elif "GAZOLE" in text or "GAZOIL" in text or "DIESEL" in text:
            return "GAZOLE"
        elif "GNR" in text:
            return "GNR"
        else:
            return "GNR"  # Par défaut
    
    def get_default_rate_by_category(self, category):
        """TAUX PAR DÉFAUT - UTILISÉS SEULEMENT EN DERNIER RECOURS"""
        default_rates = {
            "ADBLUE": 0.0,      # AdBlue non taxé
            "FIOUL_BIO": 3.86,  # Fioul agricole bio
            "FIOUL_HIVER": 3.86, # Fioul agricole hiver
            "FIOUL_STANDARD": 3.86, # Fioul agricole standard
            "GAZOLE": 24.81,    # Gazole routier
            "GNR": 24.81        # GNR standard
        }
        return default_rates.get(category, 24.81)
    
    def calculer_periodes(self):
        """Calcule automatiquement trimestre, semestre et année"""
        if self.date_mouvement:
            date_obj = getdate(self.date_mouvement)
            
            self.annee = date_obj.year
            self.trimestre = str((date_obj.month - 1) // 3 + 1)
            self.semestre = "1" if date_obj.month <= 6 else "2"
    
    def before_save(self):
        """Actions avant sauvegarde AVEC RÉCUPÉRATION DES VRAIS TAUX"""
        self.calculer_taux_et_montants()
    
    @frappe.whitelist()
    def recalculer_taux_et_montants(self):
        """
        Méthode publique pour recalculer les taux et montants
        AVEC RÉCUPÉRATION DES VRAIS TAUX
        """
        # Forcer le recalcul en remettant le taux à zéro
        ancien_taux = self.taux_gnr
        self.taux_gnr = 0
        
        # Recalculer
        self.calculer_taux_et_montants()
        
        # Sauvegarder
        self.save()
        
        return {
            "ancien_taux": ancien_taux,
            "nouveau_taux": self.taux_gnr,
            "montant_taxe_gnr": self.montant_taxe_gnr,
            "message": f"Taux recalculé: {ancien_taux} → {self.taux_gnr}€/L"
        }
    
    @frappe.whitelist()
    def analyser_sources_taux(self):
        """
        Analyse toutes les sources possibles de taux pour ce mouvement
        """
        sources = []
        
        try:
            # 1. Document de référence
            if self.reference_document and self.reference_name:
                doc_rate = self.get_taux_from_reference_document()
                sources.append({
                    "source": f"Document {self.reference_document}",
                    "valeur": doc_rate,
                    "priorite": 1,
                    "fiable": doc_rate and 0.1 <= doc_rate <= 50
                })
            
            # 2. Article maître
            item_rate = frappe.get_value("Item", self.code_produit, "gnr_tax_rate")
            sources.append({
                "source": "Article maître",
                "valeur": item_rate,
                "priorite": 2,
                "fiable": item_rate and item_rate > 0
            })
            
            # 3. Historique
            historical_rate = self.get_historical_rate_for_item()
            sources.append({
                "source": "Historique mouvements",
                "valeur": historical_rate,
                "priorite": 3,
                "fiable": historical_rate is not None
            })
            
            # 4. Factures récentes
            recent_rate = self.get_recent_invoice_rate_for_item()
            sources.append({
                "source": "Factures récentes",
                "valeur": recent_rate,
                "priorite": 4,
                "fiable": recent_rate is not None
            })
            
            # 5. Catégorie par défaut
            item_name = frappe.get_value("Item", self.code_produit, "item_name")
            category = self.detect_gnr_category_from_item(item_name)
            default_rate = self.get_default_rate_by_category(category)
            sources.append({
                "source": f"Défaut ({category})",
                "valeur": default_rate,
                "priorite": 5,
                "fiable": False  # Pas fiable car par défaut
            })
            
            # Trier par priorité
            sources.sort(key=lambda x: x["priorite"])
            
            # Identifier la meilleure source
            meilleure_source = None
            for source in sources:
                if source["fiable"] and source["valeur"]:
                    meilleure_source = source
                    break
            
            return {
                "success": True,
                "taux_actuel": self.taux_gnr,
                "sources_disponibles": sources,
                "meilleure_source": meilleure_source,
                "recommandation": self.get_recommandation_taux(sources, meilleure_source)
            }
            
        except Exception as e:
            frappe.log_error(f"Erreur analyse sources taux pour {self.name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_recommandation_taux(self, sources, meilleure_source):
        """Génère une recommandation basée sur l'analyse des sources"""
        if not meilleure_source:
            return "❌ Aucune source fiable trouvée - Vérifiez manuellement"
        
        if meilleure_source["priorite"] == 1:
            return "✅ EXCELLENT - Taux récupéré depuis la facture source"
        elif meilleure_source["priorite"] == 2:
            return "🟡 BON - Taux défini sur l'article maître"
        elif meilleure_source["priorite"] <= 4:
            return "🟠 MOYEN - Taux depuis historique ou factures récentes"
        else:
            return "🔴 SUSPECT - Taux par défaut utilisé - Vérifiez les factures"

# Fonctions utilitaires globales pour les mouvements GNR

@frappe.whitelist()
def recalculer_mouvement_specifique(movement_name):
    """
    Recalcule un mouvement spécifique avec les vrais taux
    """
    try:
        mouvement = frappe.get_doc("Mouvement GNR", movement_name)
        result = mouvement.recalculer_taux_et_montants()
        return {
            "success": True,
            "mouvement": movement_name,
            **result
        }
    except Exception as e:
        frappe.log_error(f"Erreur recalcul mouvement {movement_name}: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def recalculer_tous_mouvements_suspects(limite=100):
    """
    Recalcule tous les mouvements avec des taux suspects
    """
    try:
        # Récupérer les mouvements avec taux par défaut
        mouvements_suspects = frappe.db.sql("""
            SELECT name, code_produit, taux_gnr, quantite
            FROM `tabMouvement GNR`
            WHERE docstatus = 1
            AND taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81)  -- Taux suspects par défaut
            ORDER BY creation DESC
            LIMIT %s
        """, (limite,), as_dict=True)
        
        corriges = 0
        echecs = 0
        details = []
        
        for mouvement_data in mouvements_suspects:
            try:
                mouvement = frappe.get_doc("Mouvement GNR", mouvement_data.name)
                ancien_taux = mouvement.taux_gnr
                
                # Forcer le recalcul
                mouvement.taux_gnr = 0
                mouvement.calculer_taux_et_montants()
                
                if mouvement.taux_gnr != ancien_taux:
                    mouvement.save()
                    corriges += 1
                    details.append({
                        "mouvement": mouvement.name,
                        "article": mouvement.code_produit,
                        "ancien_taux": ancien_taux,
                        "nouveau_taux": mouvement.taux_gnr,
                        "source": "Recalcul automatique"
                    })
                
            except Exception as e:
                frappe.log_error(f"Erreur correction mouvement {mouvement_data.name}: {str(e)}")
                echecs += 1
        
        return {
            "success": True,
            "corriges": corriges,
            "echecs": echecs,
            "total_traites": len(mouvements_suspects),
            "message": f"{corriges} mouvements corrigés avec vrais taux, {echecs} échecs",
            "details_corrections": details[:10]  # Limiter les détails
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur recalcul tous mouvements suspects: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def analyser_qualite_taux_mouvements():
    """
    Analyse la qualité des taux GNR dans tous les mouvements
    """
    try:
        # Statistiques globales
        stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_mouvements,
                COUNT(CASE WHEN taux_gnr = 0 THEN 1 END) as taux_zero,
                COUNT(CASE WHEN taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as taux_suspects,
                COUNT(CASE WHEN taux_gnr > 0 AND taux_gnr NOT IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as taux_reels,
                COUNT(CASE WHEN reference_document IN ('Sales Invoice', 'Purchase Invoice') THEN 1 END) as avec_facture,
                AVG(CASE WHEN taux_gnr > 0 THEN taux_gnr END) as taux_moyen,
                MIN(CASE WHEN taux_gnr > 0 THEN taux_gnr END) as taux_min,
                MAX(taux_gnr) as taux_max,
                SUM(montant_taxe_gnr) as taxe_totale
            FROM `tabMouvement GNR`
            WHERE docstatus = 1
        """, as_dict=True)
        
        if stats:
            stat = stats[0]
            total = stat.total_mouvements or 1
            
            # Analyse par source
            par_source = frappe.db.sql("""
                SELECT 
                    CASE 
                        WHEN reference_document = 'Sales Invoice' THEN 'Factures Vente'
                        WHEN reference_document = 'Purchase Invoice' THEN 'Factures Achat' 
                        WHEN reference_document = 'Stock Entry' THEN 'Mouvements Stock'
                        ELSE 'Autres'
                    END as source,
                    COUNT(*) as nb_mouvements,
                    AVG(taux_gnr) as taux_moyen,
                    COUNT(CASE WHEN taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as nb_suspects
                FROM `tabMouvement GNR`
                WHERE docstatus = 1 AND taux_gnr > 0
                GROUP BY source
                ORDER BY nb_mouvements DESC
            """, as_dict=True)
            
            return {
                "success": True,
                "statistiques_globales": {
                    "total_mouvements": stat.total_mouvements,
                    "taux_zero": stat.taux_zero,
                    "taux_suspects": stat.taux_suspects,
                    "taux_reels": stat.taux_reels,
                    "avec_facture": stat.avec_facture,
                    "pourcentage_reels": round((stat.taux_reels / total) * 100, 1),
                    "pourcentage_suspects": round((stat.taux_suspects / total) * 100, 1),
                    "pourcentage_avec_facture": round((stat.avec_facture / total) * 100, 1),
                    "taux_moyen": round(stat.taux_moyen or 0, 3),
                    "taux_min": stat.taux_min,
                    "taux_max": stat.taux_max,
                    "taxe_totale": round(stat.taxe_totale or 0, 2)
                },
                "analyse_par_source": par_source,
                "recommandations": get_recommandations_qualite(stat, total)
            }
        
        return {"success": False, "message": "Aucune donnée trouvée"}
        
    except Exception as e:
        frappe.log_error(f"Erreur analyse qualité taux mouvements: {str(e)}")
        return {"success": False, "error": str(e)}

def get_recommandations_qualite(stat, total):
    """Génère des recommandations basées sur la qualité des taux"""
    recommandations = []
    
    pourcentage_reels = (stat.taux_reels / total) * 100
    pourcentage_suspects = (stat.taux_suspects / total) * 100
    
    if pourcentage_reels >= 80:
        recommandations.append("✅ EXCELLENTE qualité - Plus de 80% des taux sont réels")
    elif pourcentage_reels >= 60:
        recommandations.append("🟡 BONNE qualité - Plus de 60% des taux sont réels")
    else:
        recommandations.append("🔴 QUALITÉ INSUFFISANTE - Moins de 60% des taux sont réels")
    
    if pourcentage_suspects > 30:
        recommandations.append(f"⚠️ {pourcentage_suspects:.1f}% des taux sont suspects - Exécutez 'recalculer_tous_mouvements_suspects()'")
    
    if stat.taux_zero > 0:
        recommandations.append(f"ℹ️ {stat.taux_zero} mouvements avec taux zéro - Vérifiez si normal (ex: AdBlue)")
    
    pourcentage_avec_facture = (stat.avec_facture / total) * 100
    if pourcentage_avec_facture < 50:
        recommandations.append(f"📋 Seulement {pourcentage_avec_facture:.1f}% des mouvements proviennent de factures - Source la plus fiable")
    
    return recommandations

@frappe.whitelist()
def comparer_taux_article_vs_mouvements(item_code):
    """
    Compare le taux défini sur un article avec les taux utilisés dans les mouvements
    """
    try:
        # Taux de l'article
        item_rate = frappe.get_value("Item", item_code, "gnr_tax_rate")
        item_name = frappe.get_value("Item", item_code, "item_name")
        
        # Taux dans les mouvements
        mouvements_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as nb_mouvements,
                AVG(taux_gnr) as taux_moyen,
                MIN(taux_gnr) as taux_min,
                MAX(taux_gnr) as taux_max,
                COUNT(DISTINCT taux_gnr) as nb_taux_differents,
                COUNT(CASE WHEN taux_gnr IN (1.77, 3.86, 6.83, 2.84, 24.81) THEN 1 END) as nb_suspects,
                SUM(montant_taxe_gnr) as taxe_totale
            FROM `tabMouvement GNR`
            WHERE code_produit = %s AND docstatus = 1 AND taux_gnr > 0
        """, (item_code,), as_dict=True)
        
        # Répartition par source
        par_source = frappe.db.sql("""
            SELECT 
                reference_document,
                COUNT(*) as nb_mouvements,
                AVG(taux_gnr) as taux_moyen
            FROM `tabMouvement GNR`
            WHERE code_produit = %s AND docstatus = 1 AND taux_gnr > 0
            GROUP BY reference_document
            ORDER BY nb_mouvements DESC
        """, (item_code,), as_dict=True)
        
        stats = mouvements_stats[0] if mouvements_stats else {}
        
        return {
            "success": True,
            "article": {
                "code": item_code,
                "nom": item_name,
                "taux_defini": item_rate
            },
            "mouvements": stats,
            "repartition_par_source": par_source,
            "analyse": {
                "coherent": abs((stats.get("taux_moyen", 0) or 0) - (item_rate or 0)) < 0.5 if item_rate else False,
                "dispersion_elevee": (stats.get("nb_taux_differents", 0) or 0) > 3,
                "presence_suspects": (stats.get("nb_suspects", 0) or 0) > 0
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur comparaison taux article {item_code}: {str(e)}")
        return {"success": False, "error": str(e)}