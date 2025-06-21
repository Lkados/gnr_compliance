# gnr_compliance/doctype/declaration_periode_gnr/declaration_periode_gnr.py
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_months, get_first_day, get_last_day, flt
from datetime import datetime, timedelta
import json
from typing import Dict, List, Any, Optional

class DeclarationPeriodeGNR(Document):
    def validate(self):
        """Validation avant sauvegarde"""
        self.valider_periode()
        self.calculer_dates_automatiques()
        self.calculer_donnees_periode()
        
    def valider_periode(self):
        """Valide que la période est cohérente"""
        if self.type_periode == "Trimestriel":
            if self.periode not in ["T1", "T2", "T3", "T4"]:
                frappe.throw("Pour une période trimestrielle, utilisez : T1, T2, T3 ou T4")
        elif self.type_periode == "Mensuel":
            if not (self.periode.isdigit() and 1 <= int(self.periode) <= 12):
                frappe.throw("Pour une période mensuelle, utilisez : 01, 02, ..., 12")
        elif self.type_periode == "Semestriel":
            if self.periode not in ["S1", "S2"]:
                frappe.throw("Pour une période semestrielle, utilisez : S1 ou S2")
    
    def calculer_dates_automatiques(self):
        """Calcule automatiquement les dates de début et fin selon la période"""
        if not self.annee:
            frappe.throw("L'année est obligatoire")
            
        if self.type_periode == "Mensuel":
            mois = int(self.periode)
            self.date_debut = get_first_day(f"{self.annee}-{mois:02d}-01")
            self.date_fin = get_last_day(f"{self.annee}-{mois:02d}-01")
            
        elif self.type_periode == "Trimestriel":
            trimestre = int(self.periode[1])  # T1 -> 1
            mois_debut = (trimestre - 1) * 3 + 1
            self.date_debut = get_first_day(f"{self.annee}-{mois_debut:02d}-01")
            
            mois_fin = trimestre * 3
            self.date_fin = get_last_day(f"{self.annee}-{mois_fin:02d}-01")
            
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
        """Calcule toutes les données de la période"""
        if not self.date_debut or not self.date_fin:
            return
            
        # Récupérer les mouvements selon les filtres
        mouvements = self.get_mouvements_filtres()
        
        # Calculer les agrégations
        self.total_entrees = sum([m.quantite for m in mouvements if m.type_mouvement in ['Achat', 'Entrée']])
        self.total_sorties = sum([m.quantite for m in mouvements if m.type_mouvement in ['Vente', 'Sortie']])
        self.total_ventes = sum([m.quantite for m in mouvements if m.type_mouvement == 'Vente'])
        self.total_taxe_gnr = sum([m.montant_taxe_gnr or 0 for m in mouvements])
        
        # Calculer le nombre de clients uniques
        clients = set()
        for m in mouvements:
            if m.client:
                clients.add(m.client)
        self.nb_clients = len(clients)
        
        # Calculer les stocks (si période précédente existe)
        self.calculer_stocks()
        
        # Stocker les données détaillées
        self.donnees_detaillees = json.dumps(self.prepare_donnees_detaillees(mouvements))
    
    def get_mouvements_filtres(self) -> List[Any]:
        """Récupère les mouvements selon les filtres définis"""
        # Construire les conditions WHERE
        conditions = ["m.date_mouvement BETWEEN %s AND %s", "m.docstatus = 1"]
        values = [self.date_debut, self.date_fin]
        
        # Filtre par types de mouvement
        types_inclus = [t.type_mouvement for t in self.types_mouvement if t.inclus]
        if types_inclus:
            placeholders = ', '.join(['%s'] * len(types_inclus))
            conditions.append(f"m.type_mouvement IN ({placeholders})")
            values.extend(types_inclus)
        
        # Filtre par produits
        produits_inclus = [p.code_produit for p in self.produits_inclus if p.inclus]
        if produits_inclus:
            placeholders = ', '.join(['%s'] * len(produits_inclus))
            conditions.append(f"m.code_produit IN ({placeholders})")
            values.extend(produits_inclus)
        
        where_clause = " AND ".join(conditions)
        
        return frappe.db.sql(f"""
            SELECT 
                m.*,
                i.item_name,
                i.gnr_tracked_category
            FROM `tabMouvement GNR` m
            LEFT JOIN `tabItem` i ON m.code_produit = i.name
            WHERE {where_clause}
            ORDER BY m.date_mouvement, m.creation
        """, values, as_dict=True)
    
    def calculer_stocks(self):
        """Calcule les stocks de début et fin de période"""
        # Pour le stock de début, chercher la déclaration précédente
        periode_precedente = self.get_periode_precedente()
        
        if periode_precedente:
            self.stock_debut_periode = frappe.get_value(
                "Declaration Periode GNR", 
                periode_precedente, 
                "stock_fin_periode"
            ) or 0
        else:
            # Calculer depuis les mouvements historiques
            self.stock_debut_periode = self.calculer_stock_historique()
        
        # Stock de fin = début + entrées - sorties
        self.stock_fin_periode = (
            flt(self.stock_debut_periode) + 
            flt(self.total_entrees) - 
            flt(self.total_sorties)
        )
    
    def get_periode_precedente(self) -> Optional[str]:
        """Trouve la déclaration de la période précédente"""
        try:
            if self.type_periode == "Mensuel":
                mois = int(self.periode)
                if mois == 1:
                    periode_prec = "12"
                    annee_prec = self.annee - 1
                else:
                    periode_prec = f"{mois-1:02d}"
                    annee_prec = self.annee
                    
            elif self.type_periode == "Trimestriel":
                trimestre = int(self.periode[1])
                if trimestre == 1:
                    periode_prec = "T4"
                    annee_prec = self.annee - 1
                else:
                    periode_prec = f"T{trimestre-1}"
                    annee_prec = self.annee
                    
            elif self.type_periode == "Semestriel":
                semestre = int(self.periode[1])
                if semestre == 1:
                    periode_prec = "S2"
                    annee_prec = self.annee - 1
                else:
                    periode_prec = "S1"
                    annee_prec = self.annee
            else:
                return None
            
            return frappe.get_value(
                "Declaration Periode GNR",
                {
                    "type_periode": self.type_periode,
                    "periode": periode_prec,
                    "annee": annee_prec,
                    "docstatus": 1
                },
                "name"
            )
        except Exception:
            return None
    
    def calculer_stock_historique(self) -> float:
        """Calcule le stock depuis l'historique des mouvements"""
        try:
            result = frappe.db.sql("""
                SELECT 
                    SUM(CASE WHEN type_mouvement IN ('Achat', 'Entrée') THEN quantite ELSE 0 END) -
                    SUM(CASE WHEN type_mouvement IN ('Vente', 'Sortie') THEN quantite ELSE 0 END) as stock
                FROM `tabMouvement GNR`
                WHERE date_mouvement < %s AND docstatus = 1
            """, (self.date_debut,))
            
            return flt(result[0][0]) if result and result[0][0] else 0
        except Exception:
            return 0
    
    def prepare_donnees_detaillees(self, mouvements: List[Any]) -> Dict[str, Any]:
        """Prépare les données détaillées au format JSON"""
        
        # Grouper par produit
        par_produit = {}
        for mouvement in mouvements:
            code = mouvement.code_produit
            if code not in par_produit:
                par_produit[code] = {
                    'nom': mouvement.item_name,
                    'categorie': mouvement.gnr_tracked_category,
                    'entrees': 0,
                    'sorties': 0,
                    'ventes': 0,
                    'taxe': 0,
                    'mouvements': []
                }
            
            if mouvement.type_mouvement in ['Achat', 'Entrée']:
                par_produit[code]['entrees'] += flt(mouvement.quantite)
            elif mouvement.type_mouvement in ['Vente', 'Sortie']:
                par_produit[code]['sorties'] += flt(mouvement.quantite)
                
            if mouvement.type_mouvement == 'Vente':
                par_produit[code]['ventes'] += flt(mouvement.quantite)
                
            par_produit[code]['taxe'] += flt(mouvement.montant_taxe_gnr or 0)
            par_produit[code]['mouvements'].append({
                'date': str(mouvement.date_mouvement),
                'type': mouvement.type_mouvement,
                'quantite': flt(mouvement.quantite),
                'client': mouvement.client,
                'fournisseur': mouvement.fournisseur
            })
        
        # Grouper par client (pour rapports semestriels)
        par_client = {}
        if self.inclure_details_clients:
            for mouvement in mouvements:
                if mouvement.client:
                    client = mouvement.client
                    if client not in par_client:
                        par_client[client] = {
                            'nom': frappe.get_value("Customer", client, "customer_name"),
                            'quantite_totale': 0,
                            'montant_total': 0,
                            'produits': {}
                        }
                    
                    par_client[client]['quantite_totale'] += flt(mouvement.quantite)
                    par_client[client]['montant_total'] += flt(mouvement.montant_taxe_gnr or 0)
                    
                    # Détail par produit pour ce client
                    produit = mouvement.code_produit
                    if produit not in par_client[client]['produits']:
                        par_client[client]['produits'][produit] = 0
                    par_client[client]['produits'][produit] += flt(mouvement.quantite)
        
        return {
            'resume_periode': {
                'type_periode': self.type_periode,
                'periode': self.periode,
                'annee': self.annee,
                'date_debut': str(self.date_debut),
                'date_fin': str(self.date_fin),
                'total_mouvements': len(mouvements)
            },
            'par_produit': par_produit,
            'par_client': par_client,
            'conformite_reglementaire': self.verifier_conformite_reglementaire(mouvements)
        }
    
    def verifier_conformite_reglementaire(self, mouvements: List[Any]) -> Dict[str, Any]:
        """Vérifie la conformité à la réglementation française GNR"""
        conformite = {
            'statut': 'conforme',
            'alertes': [],
            'recommandations': []
        }
        
        # Vérifier les obligations trimestrielles
        if self.type_periode == "Trimestriel":
            if self.total_ventes > 0 and not self.inclure_details_clients:
                conformite['alertes'].append(
                    "Déclaration trimestrielle avec ventes : détails clients recommandés"
                )
        
        # Vérifier les obligations semestrielles (liste clients obligatoire)
        if self.type_periode == "Semestriel":
            if not self.inclure_details_clients:
                conformite['statut'] = 'non_conforme'
                conformite['alertes'].append(
                    "OBLIGATOIRE : Déclaration semestrielle doit inclure la liste des clients"
                )
            
            # Vérifier le seuil de 1000L par client
            if self.inclure_details_clients and 'par_client' in self.donnees_detaillees:
                try:
                    donnees = json.loads(self.donnees_detaillees)
                    for client, data in donnees['par_client'].items():
                        if data['quantite_totale'] >= 1000:
                            conformite['alertes'].append(
                                f"Client {client} : {data['quantite_totale']}L (>=1000L) - Déclaration spéciale requise"
                            )
                except Exception:
                    pass
        
        # Vérifier la traçabilité
        mouvements_sans_reference = [m for m in mouvements if not m.reference_name]
        if mouvements_sans_reference:
            conformite['alertes'].append(
                f"{len(mouvements_sans_reference)} mouvements sans référence document"
            )
        
        return conformite
    
    @frappe.whitelist()
    def generer_export_excel(self):
        """Génère l'export Excel selon le format réglementaire"""
        try:
            return self._generer_export_excel_detaille()
        except Exception as e:
            frappe.throw(f"Erreur génération export Excel : {str(e)}")
    
    def _generer_export_excel_detaille(self):
        """Génération Excel détaillée avec onglets multiples"""
        import xlsxwriter
        from io import BytesIO
        
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#1f4e79',
            'font_color': 'white',
            'align': 'center',
            'border': 1
        })
        
        data_format = workbook.add_format({'border': 1, 'align': 'right'})
        text_format = workbook.add_format({'border': 1})
        
        # Onglet 1: Résumé de la période
        self._creer_onglet_resume(workbook, header_format, data_format, text_format)
        
        # Onglet 2: Détail par produit
        self._creer_onglet_produits(workbook, header_format, data_format, text_format)
        
        # Onglet 3: Liste clients (si demandé)
        if self.inclure_details_clients:
            self._creer_onglet_clients(workbook, header_format, data_format, text_format)
        
        # Onglet 4: Conformité réglementaire
        self._creer_onglet_conformite(workbook, header_format, text_format)
        
        workbook.close()
        output.seek(0)
        
        # Créer le fichier
        file_name = f"Declaration_{self.type_periode}_{self.periode}_{self.annee}.xlsx"
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "attached_to_doctype": self.doctype,
            "attached_to_name": self.name,
            "content": output.getvalue()
        })
        file_doc.save()
        
        return {"file_url": file_doc.file_url, "file_name": file_name}
    
    def _creer_onglet_resume(self, workbook, header_format, data_format, text_format):
        """Crée l'onglet résumé"""
        worksheet = workbook.add_worksheet('Résumé Période')
        
        # En-tête
        worksheet.merge_range('A1:G1', 
            f'DÉCLARATION {self.type_periode.upper()} GNR - {self.periode} {self.annee}', 
            header_format)
        
        # Informations générales
        row = 3
        info_data = [
            ['Période', f'{self.type_periode} {self.periode}/{self.annee}'],
            ['Date début', str(self.date_debut)],
            ['Date fin', str(self.date_fin)],
            ['Stock début (L)', self.stock_debut_periode],
            ['Total entrées (L)', self.total_entrees],
            ['Total sorties (L)', self.total_sorties],
            ['Stock fin (L)', self.stock_fin_periode],
            ['Total taxe GNR (€)', self.total_taxe_gnr],
            ['Nombre de clients', self.nb_clients]
        ]
        
        for label, value in info_data:
            worksheet.write(row, 0, label, text_format)
            worksheet.write(row, 1, value, data_format)
            row += 1
    
    def _creer_onglet_produits(self, workbook, header_format, data_format, text_format):
        """Crée l'onglet détail par produit"""
        worksheet = workbook.add_worksheet('Détail Produits')
        
        # En-têtes
        headers = ['Code Produit', 'Nom', 'Catégorie GNR', 'Entrées (L)', 
                  'Sorties (L)', 'Ventes (L)', 'Taxe GNR (€)']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Données des produits
        try:
            donnees = json.loads(self.donnees_detaillees or '{}')
            par_produit = donnees.get('par_produit', {})
            
            row = 1
            for code_produit, data in par_produit.items():
                worksheet.write(row, 0, code_produit, text_format)
                worksheet.write(row, 1, data.get('nom', ''), text_format)
                worksheet.write(row, 2, data.get('categorie', ''), text_format)
                worksheet.write(row, 3, data.get('entrees', 0), data_format)
                worksheet.write(row, 4, data.get('sorties', 0), data_format)
                worksheet.write(row, 5, data.get('ventes', 0), data_format)
                worksheet.write(row, 6, data.get('taxe', 0), data_format)
                row += 1
                
        except Exception as e:
            worksheet.write(1, 0, f"Erreur chargement données : {str(e)}", text_format)
    
    def _creer_onglet_clients(self, workbook, header_format, data_format, text_format):
        """Crée l'onglet liste clients (obligatoire pour semestriel)"""
        worksheet = workbook.add_worksheet('Liste Clients')
        
        # En-têtes
        headers = ['Code Client', 'Nom Client', 'Quantité Totale (L)', 'Montant Total (€)']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Données clients
        try:
            donnees = json.loads(self.donnees_detaillees or '{}')
            par_client = donnees.get('par_client', {})
            
            row = 1
            for code_client, data in par_client.items():
                worksheet.write(row, 0, code_client, text_format)
                worksheet.write(row, 1, data.get('nom', ''), text_format)
                worksheet.write(row, 2, data.get('quantite_totale', 0), data_format)
                worksheet.write(row, 3, data.get('montant_total', 0), data_format)
                row += 1
                
        except Exception as e:
            worksheet.write(1, 0, f"Erreur chargement données clients : {str(e)}", text_format)
    
    def _creer_onglet_conformite(self, workbook, header_format, text_format):
        """Crée l'onglet conformité réglementaire"""
        worksheet = workbook.add_worksheet('Conformité')
        
        worksheet.write(0, 0, 'VÉRIFICATION CONFORMITÉ RÉGLEMENTAIRE', header_format)
        
        try:
            donnees = json.loads(self.donnees_detaillees or '{}')
            conformite = donnees.get('conformite_reglementaire', {})
            
            row = 2
            worksheet.write(row, 0, f"Statut : {conformite.get('statut', 'inconnu').upper()}", text_format)
            row += 2
            
            # Alertes
            alertes = conformite.get('alertes', [])
            if alertes:
                worksheet.write(row, 0, 'ALERTES :', text_format)
                row += 1
                for alerte in alertes:
                    worksheet.write(row, 0, f"• {alerte}", text_format)
                    row += 1
            
            # Recommandations
            recommandations = conformite.get('recommandations', [])
            if recommandations:
                row += 1
                worksheet.write(row, 0, 'RECOMMANDATIONS :', text_format)
                row += 1
                for reco in recommandations:
                    worksheet.write(row, 0, f"• {reco}", text_format)
                    row += 1
                    
        except Exception as e:
            worksheet.write(2, 0, f"Erreur chargement conformité : {str(e)}", text_format)