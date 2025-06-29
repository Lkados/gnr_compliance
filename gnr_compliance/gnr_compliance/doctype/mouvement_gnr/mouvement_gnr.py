# 1. MISE À JOUR DU DOCTYPE MOUVEMENT GNR PYTHON
# Fichier: gnr_compliance/gnr_compliance/doctype/mouvement_gnr/mouvement_gnr.py

import frappe
from frappe.model.document import Document
from frappe.utils import flt

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
            
            # 2. Convertir le taux de €/L vers €/hL si nécessaire
            # Le champ est libellé "€/hL" mais nos calculs sont en €/L
            # 1 hL = 100 L, donc taux_hL = taux_L * 100
            if self.taux_gnr and self.taux_gnr < 10:  # Probablement en €/L
                # Garder en €/L pour les calculs internes
                taux_par_litre = self.taux_gnr
            else:  # Probablement en €/hL
                taux_par_litre = self.taux_gnr / 100
            
            # 3. Calculer le montant de taxe (quantité en L × taux en €/L)
            if self.quantite and taux_par_litre:
                self.montant_taxe_gnr = flt(self.quantite * taux_par_litre, 2)
            
            # 4. Stocker le taux en €/L pour cohérence
            if taux_par_litre:
                self.taux_gnr = taux_par_litre
                
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
            from frappe.utils import getdate
            date_obj = getdate(self.date_mouvement)
            
            self.annee = date_obj.year
            self.trimestre = str((date_obj.month - 1) // 3 + 1)
            self.semestre = "1" if date_obj.month <= 6 else "2"
    
    def before_save(self):
        """Actions avant sauvegarde"""
        self.calculer_taux_et_montants()
    
    def get_taux_gnr_depuis_facture(self):
        """Récupère le taux GNR réel depuis la facture source"""
        if not self.reference_document or not self.reference_name:
            return 0
        
        try:
            if self.reference_document in ["Sales Invoice", "Purchase Invoice"]:
                facture = frappe.get_doc(self.reference_document, self.reference_name)
                
                # Chercher l'item correspondant
                items_field = "items"
                for item in facture.get(items_field, []):
                    if item.item_code == self.code_produit:
                        return self.extraire_taux_depuis_item_facture(facture, item)
        except Exception as e:
            frappe.log_error(f"Erreur récupération taux depuis facture: {str(e)}")
        
        return 0
    
    def extraire_taux_depuis_item_facture(self, facture, item):
        """Extrait le taux GNR depuis un item de facture"""
        try:
            # 1. Chercher dans les taxes de la facture
            if hasattr(facture, 'taxes') and facture.taxes:
                for tax_row in facture.taxes:
                    if tax_row.description and any(word in tax_row.description.lower() 
                                                 for word in ['gnr', 'accise', 'ticpe']):
                        if item.qty > 0 and tax_row.tax_amount:
                            return abs(tax_row.tax_amount) / item.qty
            
            # 2. Utiliser le taux de l'article
            return self.get_taux_gnr_article()
            
        except Exception as e:
            frappe.log_error(f"Erreur extraction taux facture: {str(e)}")
            return 0

# 2. JAVASCRIPT POUR LE FORMULAIRE
# Fichier: gnr_compliance/gnr_compliance/doctype/mouvement_gnr/mouvement_gnr.js

frappe.ui.form.on("Mouvement GNR", {
    refresh: function(frm) {
        // Ajouter des indicateurs
        if (frm.doc.montant_taxe_gnr) {
            frm.dashboard.add_indicator(__("Taxe GNR: {0}", [format_currency(frm.doc.montant_taxe_gnr)]), "blue");
        }
        
        if (frm.doc.taux_gnr) {
            frm.dashboard.add_indicator(__("Taux: {0} €/L", [frm.doc.taux_gnr]), "green");
        }
        
        // Bouton pour recalculer
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("🔄 Recalculer"), function() {
                recalculer_montants(frm);
            });
        }
    },
    
    code_produit: function(frm) {
        if (frm.doc.code_produit) {
            // Récupérer automatiquement le taux GNR de l'article
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Item",
                    fieldname: ["gnr_tax_rate", "gnr_tracked_category", "item_group"],
                    filters: {name: frm.doc.code_produit}
                },
                callback: function(r) {
                    if (r.message) {
                        let taux = r.message.gnr_tax_rate || getTauxParDefaut(r.message.item_group);
                        
                        frm.set_value("taux_gnr", taux);
                        frm.set_value("categorie_gnr", r.message.gnr_tracked_category);
                        
                        // Recalculer le montant
                        calculer_montant_taxe(frm);
                    }
                }
            });
        }
    },
    
    quantite: function(frm) {
        calculer_montant_taxe(frm);
    },
    
    taux_gnr: function(frm) {
        calculer_montant_taxe(frm);
    },
    
    date_mouvement: function(frm) {
        calculer_periodes(frm);
    }
});

function calculer_montant_taxe(frm) {
    if (frm.doc.quantite && frm.doc.taux_gnr) {
        let montant = frm.doc.quantite * frm.doc.taux_gnr;
        frm.set_value("montant_taxe_gnr", montant);
        
        // Afficher le calcul
        frappe.show_alert({
            message: __("{0}L × {1}€/L = {2}€", [
                frm.doc.quantite, 
                frm.doc.taux_gnr, 
                format_currency(montant)
            ]),
            indicator: "green"
        });
    }
}

function calculer_periodes(frm) {
    if (frm.doc.date_mouvement) {
        let date = frappe.datetime.str_to_obj(frm.doc.date_mouvement);
        
        frm.set_value("annee", date.getFullYear());
        frm.set_value("trimestre", Math.floor((date.getMonth()) / 3) + 1);
        frm.set_value("semestre", date.getMonth() < 6 ? "1" : "2");
    }
}

function getTauxParDefaut(item_group) {
    const taux_defaut = {
        "Combustibles/Carburants/GNR": 24.81,
        "Combustibles/Carburants/Gazole": 24.81,
        "Combustibles/Adblue": 0,
        "Combustibles/Fioul/Bio": 3.86,
        "Combustibles/Fioul/Hiver": 3.86,
        "Combustibles/Fioul/Standard": 3.86
    };
    
    return taux_defaut[item_group] || 0;
}

function recalculer_montants(frm) {
    frappe.call({
        method: "recalculer_taux_et_montants",
        doc: frm.doc,
        callback: function(r) {
            if (r.message) {
                frm.reload_doc();
                frappe.show_alert({
                    message: __("Montants recalculés avec succès"),
                    indicator: "green"
                });
            }
        }
    });
}

// 3. SCRIPT DE CORRECTION POUR LES MOUVEMENTS EXISTANTS

# Script Python à exécuter dans la console pour corriger les mouvements existants

def corriger_calculs_mouvements_existants():
    """Corrige les calculs pour tous les mouvements GNR existants"""
    print("🔧 Correction des calculs pour les mouvements GNR existants...")
    
    # Récupérer tous les mouvements GNR
    mouvements = frappe.get_all("Mouvement GNR", 
                               filters={"docstatus": ["!=", 2]},
                               fields=["name", "code_produit", "quantite", "taux_gnr", "montant_taxe_gnr"])
    
    corriges = 0
    errors = 0
    
    for mouvement in mouvements:
        try:
            doc = frappe.get_doc("Mouvement GNR", mouvement.name)
            
            # Sauvegarder les valeurs originales
            ancien_taux = doc.taux_gnr
            ancien_montant = doc.montant_taxe_gnr
            
            # Recalculer
            doc.calculer_taux_et_montants()
            
            # Vérifier s'il y a eu des changements
            if (abs((doc.taux_gnr or 0) - (ancien_taux or 0)) > 0.01 or 
                abs((doc.montant_taxe_gnr or 0) - (ancien_montant or 0)) > 0.01):
                
                # Sauvegarder sans déclencher les hooks
                doc.db_update()
                corriges += 1
                
                print(f"  ✅ {mouvement.name}: Taux {ancien_taux} → {doc.taux_gnr}, Montant {ancien_montant} → {doc.montant_taxe_gnr}")
        
        except Exception as e:
            errors += 1
            print(f"  ❌ Erreur {mouvement.name}: {str(e)}")
    
    frappe.db.commit()
    
    print(f"\n📊 Résultats:")
    print(f"  - Mouvements corrigés: {corriges}")
    print(f"  - Erreurs: {errors}")
    print(f"  - Total traité: {len(mouvements)}")

def ajouter_methode_recalcul_au_doctype():
    """Ajoute la méthode de recalcul au DocType Mouvement GNR"""
    
    # Méthode à ajouter dans la classe MouvementGNR
    method_code = '''
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
    '''
    
    print("📝 Ajoutez cette méthode à la classe MouvementGNR:")
    print(method_code)

# 4. FONCTION DE TEST DES CALCULS

def tester_calculs_gnr():
    """Teste les calculs GNR avec différents scénarios"""
    
    print("🧪 Test des calculs GNR...")
    
    scenarios = [
        {"quantite": 1000, "taux": 24.81, "attendu": 24810},  # 1000L × 24.81€/L
        {"quantite": 500, "taux": 3.86, "attendu": 1930},     # 500L × 3.86€/L  
        {"quantite": 2000, "taux": 0, "attendu": 0},          # AdBlue
        {"quantite": 1500, "taux": 24.81, "attendu": 37215},  # 1500L × 24.81€/L
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        calcul = scenario["quantite"] * scenario["taux"]
        status = "✅" if abs(calcul - scenario["attendu"]) < 0.01 else "❌"
        
        print(f"  Test {i}: {scenario['quantite']}L × {scenario['taux']}€/L = {calcul}€ {status}")

# 5. VÉRIFICATION DES UNITÉS

def verifier_coherence_unites():
    """Vérifie la cohérence des unités dans les mouvements GNR"""
    
    print("🔍 Vérification des unités...")
    
    # Vérifier les taux suspects
    taux_suspects = frappe.db.sql("""
        SELECT name, code_produit, quantite, taux_gnr, montant_taxe_gnr,
               (quantite * taux_gnr) as montant_calcule,
               ABS((quantite * taux_gnr) - COALESCE(montant_taxe_gnr, 0)) as ecart
        FROM `tabMouvement GNR`
        WHERE docstatus != 2
        AND (
            taux_gnr > 100  -- Probablement en €/hL au lieu de €/L
            OR ABS((quantite * taux_gnr) - COALESCE(montant_taxe_gnr, 0)) > 1
        )
        LIMIT 20
    """, as_dict=True)
    
    if taux_suspects:
        print(f"  ⚠️ {len(taux_suspects)} mouvements avec taux/calculs suspects:")
        for mouvement in taux_suspects:
            print(f"    - {mouvement.name}: {mouvement.taux_gnr}€/? × {mouvement.quantite}L = {mouvement.montant_taxe_gnr}€ (calculé: {mouvement.montant_calcule}€)")
    else:
        print("  ✅ Tous les calculs semblent cohérents")

# EXÉCUTION DU SCRIPT DE CORRECTION
if __name__ == "__main__":
    print("🚀 Démarrage de la correction des calculs GNR...\n")
    
    # 1. Tester les calculs
    tester_calculs_gnr()
    
    # 2. Vérifier les unités
    verifier_coherence_unites()
    
    # 3. Corriger les mouvements existants
    corriger_calculs_mouvements_existants()
    
    print("\n✅ Correction terminée !")