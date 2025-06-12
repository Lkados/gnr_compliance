// public/js/export_dialog.js
class GNRExportDialog {
    constructor(doctype, filters) {
        this.doctype = doctype;
        this.filters = filters;
        this.setup_dialog();
    }
    
    setup_dialog() {
        this.dialog = new frappe.ui.Dialog({
            title: 'Exporter Données GNR',
            fields: [
                {
                    fieldtype: 'Select',
                    fieldname: 'export_format',
                    label: 'Format d\'Export',
                    options: [
                        'Excel (XLSX) - Arrêté Trimestriel',
                        'CSV - Liste Clients Semestrielle', 
                        'PDF - Rapport Détaillé',
                        'XML - Format DGDDI'
                    ],
                    reqd: 1
                },
                {
                    fieldtype: 'Select',
                    fieldname: 'periode_type',
                    label: 'Type de Période',
                    options: ['Trimestrielle', 'Semestrielle', 'Annuelle'],
                    depends_on: 'eval:doc.export_format'
                },
                {
                    fieldtype: 'Date',
                    fieldname: 'from_date',
                    label: 'Date de Début',
                    reqd: 1
                },
                {
                    fieldtype: 'Date',
                    fieldname: 'to_date',
                    label: 'Date de Fin',
                    reqd: 1
                },
                {
                    fieldtype: 'Check',
                    fieldname: 'inclure_details',
                    label: 'Inclure Détails par Client'
                }
            ],
            primary_action_label: 'Exporter',
            primary_action: () => this.start_export()
        });
    }
    
    start_export() {
        const values = this.dialog.get_values();
        if (!values) return;
        
        frappe.call({
            method: 'gnr_compliance.api.generate_export',
            args: {
                export_format: values.export_format,
                from_date: values.from_date,
                to_date: values.to_date,
                periode_type: values.periode_type,
                inclure_details: values.inclure_details
            },
            callback: (r) => {
                if (r.message && r.message.file_url) {
                    window.open(r.message.file_url);
                    this.dialog.hide();
                }
            }
        });
    }
}