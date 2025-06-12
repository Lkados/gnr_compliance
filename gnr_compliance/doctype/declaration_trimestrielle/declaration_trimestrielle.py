# gnr_compliance/doctype/declaration_trimestrielle/declaration_trimestrielle.py
import frappe
from frappe.model.document import Document
import json
from datetime import datetime, timedelta

class DeclarationTrimestrielle(Document):
    def validate(self):
        self.calculer_donnees_trimestre()
        self.valider_coherence_donnees()
    
    def calculer_donnees_trimestre(self):
        """Calcul automatique des données trimestrielles"""
        # Récupérer tous les mouvements du trimestre
        mouvements = frappe.get_all("Mouvement GNR",
            filters={
                "trimestre": self.trimestre,
                "annee": self.annee,
                "docstatus": 1
            },
            fields=["*"]
        )
        
        # Calculs d'agrégation
        self.stock_debut_trimestre = self.calculer_stock_debut()
        self.total_entrees = sum([m.quantite for m in mouvements if m.type_mouvement == "Entrée"])
        self.total_sorties = sum([m.quantite for m in mouvements if m.type_mouvement == "Sortie"])
        self.stock_fin_trimestre = self.stock_debut_trimestre + self.total_entrees - self.total_sorties
        
        # Détail par type de produit
        self.detail_produits = self.calculer_detail_produits(mouvements)
    
    def calculer_stock_debut(self):
        """Calculer le stock de début de trimestre"""
        # Récupérer la déclaration du trimestre précédent
        trimestre_precedent = self.trimestre - 1 if self.trimestre > 1 else 4
        annee_precedente = self.annee if self.trimestre > 1 else self.annee - 1
        
        declaration_precedente = frappe.get_value("Déclaration Trimestrielle",
            filters={
                "trimestre": trimestre_precedent,
                "annee": annee_precedente,
                "docstatus": 1
            },
            fieldname="stock_fin_trimestre"
        )
        
        return declaration_precedente or 0
    
    def generer_export_excel(self):
        """Génération de l'export Excel selon le format réglementaire"""
        import xlsxwriter
        from io import BytesIO
        
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Feuille principale - Arrêté de stock détaillé
        worksheet = workbook.add_worksheet('Arrêté Stock Détaillé')
        
        # Formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4CAF50',
            'font_color': 'white',
            'align': 'center',
            'border': 1
        })
        
        data_format = workbook.add_format({
            'border': 1,
            'align': 'right'
        })
        
        # En-têtes
        headers = [
            'Code Produit', 'Désignation', 'Stock Début', 
            'Entrées', 'Sorties', 'Stock Fin', 'Taux GNR (€/hL)'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Données
        detail_produits = json.loads(self.detail_produits or "[]")
        for row, produit in enumerate(detail_produits, 1):
            worksheet.write(row, 0, produit['code'])
            worksheet.write(row, 1, produit['designation'])
            worksheet.write(row, 2, produit['stock_debut'], data_format)
            worksheet.write(row, 3, produit['entrees'], data_format)
            worksheet.write(row, 4, produit['sorties'], data_format)
            worksheet.write(row, 5, produit['stock_fin'], data_format)
            worksheet.write(row, 6, produit['taux_gnr'], data_format)
        
        workbook.close()
        output.seek(0)
        
        # Sauvegarder le fichier
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"Declaration_T{self.trimestre}_{self.annee}.xlsx",
            "attached_to_doctype": self.doctype,
            "attached_to_name": self.name,
            "content": output.getvalue()
        })
        file_doc.save()
        
        return file_doc.file_url