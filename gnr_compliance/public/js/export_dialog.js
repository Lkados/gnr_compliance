// public/js/export_dialog.js
class GNRExportDialog {
    constructor(doctype, filters) {
        this.doctype = doctype;
        this.filters = filters;
        this.setup_dialog();
    }
    
    setup_dialog() {
        this.dialog = new frappe.ui.Dialog({
            title: 'Exporter Déclarations GNR - Format Officiel',
            size: 'large',
            fields: [
                {
                    fieldtype: 'Select',
                    fieldname: 'declaration_type',
                    label: 'Type de Déclaration',
                    options: [
                        '',
                        'Arrêté Trimestriel de Stock',
                        'Liste Semestrielle des Clients'
                    ],
                    reqd: 1,
                    change: () => this.update_period_options()
                },
                {
                    fieldtype: 'Column Break'
                },
                {
                    fieldtype: 'HTML',
                    fieldname: 'declaration_info',
                    label: 'Informations',
                    options: '<div id="declaration-info" style="padding: 10px; background: #f8f9fa; border-radius: 4px; margin-bottom: 10px;"></div>'
                },
                {
                    fieldtype: 'Section Break',
                    label: 'Période de Déclaration'
                },
                {
                    fieldtype: 'Select',
                    fieldname: 'period_selection',
                    label: 'Sélection de Période',
                    options: ['Prédéfinie', 'Personnalisée'],
                    default: 'Prédéfinie',
                    change: () => this.update_period_fields()
                },
                {
                    fieldtype: 'Column Break'
                },
                {
                    fieldtype: 'Select',
                    fieldname: 'predefined_period',
                    label: 'Période',
                    options: '',
                    depends_on: 'eval:doc.period_selection=="Prédéfinie"'
                },
                {
                    fieldtype: 'Date',
                    fieldname: 'custom_from_date',
                    label: 'Date de Début',
                    depends_on: 'eval:doc.period_selection=="Personnalisée"'
                },
                {
                    fieldtype: 'Date',
                    fieldname: 'custom_to_date',
                    label: 'Date de Fin',
                    depends_on: 'eval:doc.period_selection=="Personnalisée"'
                },
                {
                    fieldtype: 'Section Break',
                    label: 'Prévisualisation'
                },
                {
                    fieldtype: 'HTML',
                    fieldname: 'preview_area',
                    options: '<div id="preview-area" style="min-height: 200px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;"><em>Sélectionnez un type de déclaration et une période pour voir la prévisualisation</em></div>'
                }
            ],
            primary_action_label: 'Générer et Télécharger',
            primary_action: () => this.generate_declaration(),
            secondary_action_label: 'Prévisualiser',
            secondary_action: () => this.preview_declaration()
        });
        
        // Charger les périodes disponibles
        this.load_available_periods();
    }
    
    load_available_periods() {
        frappe.call({
            method: 'gnr_compliance.api_excel.get_available_periods',
            callback: (r) => {
                if (r.message) {
                    this.available_periods = r.message;
                    this.update_period_options();
                }
            }
        });
    }
    
    update_period_options() {
        const declaration_type = this.dialog.get_value('declaration_type');
        let info_html = '';
        let period_options = [''];
        
        if (declaration_type === 'Arrêté Trimestriel de Stock') {
            info_html = `
                <strong>Arrêté Trimestriel de Stock</strong><br>
                • Format officiel DGDDI<br>
                • Comptabilité matière jour par jour<br>
                • Stocks, entrées, sorties avec formules Excel<br>
                • Récapitulatif trimestriel automatique
            `;
            
            if (this.available_periods && this.available_periods.quarters) {
                period_options = [''].concat(
                    this.available_periods.quarters.map(q => q.label)
                );
            }
            
        } else if (declaration_type === 'Liste Semestrielle des Clients') {
            info_html = `
                <strong>Liste Semestrielle des Clients</strong><br>
                • Format officiel douanier<br>
                • Informations clients avec SIREN<br>
                • Volumes livrés en hectolitres<br>
                • Tarifs d'accise automatiques (3.86€ agricole, 24.81€ autres)
            `;
            
            if (this.available_periods && this.available_periods.semesters) {
                period_options = [''].concat(
                    this.available_periods.semesters.map(s => s.label)
                );
            }
        }
        
        // Mettre à jour les informations
        this.dialog.fields_dict.declaration_info.$wrapper.find('#declaration-info').html(info_html);
        
        // Mettre à jour les options de période
        this.dialog.set_df_property('predefined_period', 'options', period_options);
    }
    
    update_period_fields() {
        const period_selection = this.dialog.get_value('period_selection');
        // Les champs sont déjà gérés par depends_on
    }
    
    preview_declaration() {
        const values = this.dialog.get_values();
        if (!values || !values.declaration_type) {
            frappe.msgprint('Veuillez sélectionner un type de déclaration');
            return;
        }
        
        let period_start, period_end;
        
        if (values.period_selection === 'Prédéfinie' && values.predefined_period) {
            const selected_period = this.get_period_dates(values.declaration_type, values.predefined_period);
            if (selected_period) {
                period_start = selected_period.start_date;
                period_end = selected_period.end_date;
            }
        } else if (values.period_selection === 'Personnalisée') {
            period_start = values.custom_from_date;
            period_end = values.custom_to_date;
        }
        
        if (!period_start || !period_end) {
            frappe.msgprint('Veuillez sélectionner une période valide');
            return;
        }
        
        const declaration_type = values.declaration_type === 'Arrêté Trimestriel de Stock' ? 'arrete_trimestriel' : 'liste_clients';
        
        frappe.call({
            method: 'gnr_compliance.api_excel.preview_declaration_data',
            args: {
                declaration_type: declaration_type,
                period_start: period_start,
                period_end: period_end
            },
            callback: (r) => {
                if (r.message) {
                    this.show_preview(r.message);
                }
            }
        });
    }
    
    show_preview(data) {
        let preview_html = `
            <div style="margin-bottom: 15px;">
                <strong>Période:</strong> ${data.period_start} au ${data.period_end}
            </div>
        `;
        
        if (data.type === 'arrete_trimestriel') {
            preview_html += `
                <div class="row">
                    <div class="col-md-6">
                        <h6>Résumé des Mouvements</h6>
                        <table class="table table-sm">
                            <tr><td>Total Entrées:</td><td>${data.summary.total_entrees.toFixed(0)} L</td></tr>
                            <tr><td>Sorties Agricoles:</td><td>${data.summary.total_sorties_agricole.toFixed(0)} L</td></tr>
                            <tr><td>Sorties Autres:</td><td>${data.summary.total_sorties_sans_attestation.toFixed(0)} L</td></tr>
                            <tr><td><strong>Variation Stock:</strong></td><td><strong>${data.summary.stock_variation.toFixed(0)} L</strong></td></tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <h6>Premiers Mouvements (${data.total_movements} total)</h6>
                        <table class="table table-sm">
                            <thead>
                                <tr><th>Date</th><th>Entrées</th><th>Sorties Agri.</th><th>Sorties Autres</th></tr>
                            </thead>
                            <tbody>
            `;
            
            data.movements.forEach(m => {
                preview_html += `<tr>
                    <td>${m.date}</td>
                    <td>${m.entrees.toFixed(0)}</td>
                    <td>${m.sorties_agricole.toFixed(0)}</td>
                    <td>${m.sorties_sans_attestation.toFixed(0)}</td>
                </tr>`;
            });
            
            preview_html += `</tbody></table></div></div>`;
            
        } else if (data.type === 'liste_clients') {
            preview_html += `
                <div class="row">
                    <div class="col-md-6">
                        <h6>Résumé Clients</h6>
                        <table class="table table-sm">
                            <tr><td>Clients Agricoles:</td><td>${data.summary.nb_clients_agricole}</td></tr>
                            <tr><td>Autres Clients:</td><td>${data.summary.nb_clients_autres}</td></tr>
                            <tr><td><strong>Total Clients:</strong></td><td><strong>${data.summary.total_clients}</strong></td></tr>
                            <tr><td><strong>Volume Total:</strong></td><td><strong>${data.summary.total_volume_hl.toFixed(2)} hL</strong></td></tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <h6>Premiers Clients (${data.total_clients} total)</h6>
                        <table class="table table-sm">
                            <thead>
                                <tr><th>Client</th><th>Volume (hL)</th><th>Tarif €/hL</th></tr>
                            </thead>
                            <tbody>
            `;
            
            data.clients.forEach(c => {
                preview_html += `<tr>
                    <td>${c.raison_sociale}</td>
                    <td>${c.volume_hl.toFixed(2)}</td>
                    <td>${c.tarif_accise.toFixed(2)}</td>
                </tr>`;
            });
            
            preview_html += `</tbody></table></div></div>`;
        }
        
        this.dialog.fields_dict.preview_area.$wrapper.find('#preview-area').html(preview_html);
    }
    
    generate_declaration() {
        const values = this.dialog.get_values();
        if (!values || !values.declaration_type) {
            frappe.msgprint('Veuillez sélectionner un type de déclaration');
            return;
        }
        
        let period_start, period_end;
        let api_method, api_args = {};
        
        if (values.period_selection === 'Prédéfinie' && values.predefined_period) {
            const selected_period = this.get_period_dates(values.declaration_type, values.predefined_period);
            if (selected_period) {
                period_start = selected_period.start_date;
                period_end = selected_period.end_date;
                
                if (values.declaration_type === 'Arrêté Trimestriel de Stock') {
                    api_args.quarter = selected_period.quarter;
                    api_args.year = selected_period.year;
                } else {
                    api_args.semester = selected_period.semester;
                    api_args.year = selected_period.year;
                }
            }
        } else if (values.period_selection === 'Personnalisée') {
            period_start = values.custom_from_date;
            period_end = values.custom_to_date;
            api_args.period_start = period_start;
            api_args.period_end = period_end;
        }
        
        if (!period_start || !period_end) {
            frappe.msgprint('Veuillez sélectionner une période valide');
            return;
        }
        
        // Déterminer l'API à appeler
        if (values.declaration_type === 'Arrêté Trimestriel de Stock') {
            api_method = 'gnr_compliance.api_excel.download_arrete_trimestriel';
        } else {
            api_method = 'gnr_compliance.api_excel.download_liste_clients';
        }
        
        // Afficher un indicateur de chargement
        frappe.show_progress('Génération du fichier Excel...', 50, 100, 'Veuillez patienter');
        
        // Générer et télécharger le fichier
        frappe.call({
            method: api_method,
            args: api_args,
            callback: (r) => {
                frappe.hide_progress();
                this.dialog.hide();
                frappe.show_alert({
                    message: 'Fichier Excel généré avec succès !',
                    indicator: 'green'
                });
            },
            error: (r) => {
                frappe.hide_progress();
                frappe.msgprint('Erreur lors de la génération du fichier');
            }
        });
    }
    
    get_period_dates(declaration_type, period_label) {
        if (declaration_type === 'Arrêté Trimestriel de Stock' && this.available_periods.quarters) {
            return this.available_periods.quarters.find(q => q.label === period_label);
        } else if (declaration_type === 'Liste Semestrielle des Clients' && this.available_periods.semesters) {
            return this.available_periods.semesters.find(s => s.label === period_label);
        }
        return null;
    }
    
    show() {
        this.dialog.show();
    }
}