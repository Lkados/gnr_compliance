// Customisation de la ListView pour Mouvement GNR
frappe.listview_settings['Mouvement GNR'] = {
    onload: function(listview) {
        // Ajouter les boutons d'export personnalisés
        listview.page.add_button(
            __('Exporter Déclarations Officielles'), 
            () => {
                const export_dialog = new GNRExportDialog('Mouvement GNR', listview.get_filters());
                export_dialog.show();
            }, 
            'primary'
        );

        // Bouton pour soumettre tous les mouvements en attente
        listview.page.add_button(
            __('Soumettre Tous les Brouillons'), 
            () => {
                gnr_compliance.utils.submit_pending_movements();
            }, 
            'secondary'
        );
        
        // Bouton pour vérifier la cohérence des données
        listview.page.add_button(
            __('Vérifier Cohérence'), 
            () => {
                frappe.call({
                    method: 'gnr_compliance.utils.gnr_validation.verify_data_consistency',
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: 'Vérification des données',
                                message: r.message.summary,
                                indicator: r.message.has_errors ? 'red' : 'green'
                            });
                        }
                    }
                });
            },
            'light'
        );
    },

    // Personnaliser les colonnes affichées
    add_fields: ['purpose', 'customer_category', 'qty_in_liters', 'customer', 'date'],
    
    // Formatage personnalisé des colonnes
    formatters: {
        qty_in_liters: function(value) {
            return value ? `${flt(value, 0)} L` : '';
        },
        customer_category: function(value) {
            if (value === 'Agricole') {
                return `<span class="indicator green">${value}</span>`;
            } else if (value) {
                return `<span class="indicator blue">${value}</span>`;
            }
            return '';
        },
        purpose: function(value) {
            const colors = {
                'Receipt': 'green',
                'Material Issue': 'orange',
                'Material Transfer': 'blue'
            };
            const color = colors[value] || 'grey';
            return `<span class="indicator ${color}">${value}</span>`;
        }
    },

    // Actions personnalisées sur les lignes
    get_indicator: function(doc) {
        if (doc.docstatus === 0) {
            return [__('Brouillon'), 'orange', 'docstatus,=,0'];
        } else if (doc.docstatus === 1) {
            return [__('Soumis'), 'green', 'docstatus,=,1'];
        } else if (doc.docstatus === 2) {
            return [__('Annulé'), 'red', 'docstatus,=,2'];
        }
    },

    // Filtrages rapides
    button: {
        show: function(doc) {
            return doc.docstatus !== 2;
        },
        get_label: function() {
            return __('Actions');
        },
        get_description: function(doc) {
            return __('Actions pour {0}', [doc.name.bold()]);
        },
        action: function(doc) {
            frappe.set_route('Form', doc.doctype, doc.name);
        }
    }
};

// Ajouter des statistiques rapides dans la sidebar
frappe.provide("frappe.views");

frappe.views.ListSidebar = frappe.views.ListSidebar.extend({
    make_stats: function() {
        this._super();
        
        // Ajouter des stats GNR spécifiques
        if (this.page.list.doctype === 'Mouvement GNR') {
            this.add_gnr_stats();
        }
    },
    
    add_gnr_stats: function() {
        const $stats = $('<div class="sidebar-stat"><h6>Statistiques GNR</h6></div>');
        
        // Statistiques pour le mois en cours
        frappe.call({
            method: 'gnr_compliance.api.get_monthly_stats',
            callback: (r) => {
                if (r.message) {
                    const stats = r.message;
                    $stats.append(`
                        <div class="stat-row">
                            <div class="stat-label">Stock Actuel</div>
                            <div class="stat-value">${stats.current_stock || 0} L</div>
                        </div>
                        <div class="stat-row">
                            <div class="stat-label">Entrées ce mois</div>
                            <div class="stat-value">${stats.monthly_receipts || 0} L</div>
                        </div>
                        <div class="stat-row">
                            <div class="stat-label">Sorties ce mois</div>
                            <div class="stat-value">${stats.monthly_issues || 0} L</div>
                        </div>
                        <div class="stat-row">
                            <div class="stat-label">Clients Actifs</div>
                            <div class="stat-value">${stats.active_customers || 0}</div>
                        </div>
                    `);
                }
                
                this.$sidebar.find('.list-tags').after($stats);
            }
        });
    }
});

// Ajouter des raccourcis clavier
$(document).on('keydown', function(e) {
    // Ctrl + E pour ouvrir les exports
    if (e.ctrlKey && e.key === 'e' && cur_list && cur_list.doctype === 'Mouvement GNR') {
        e.preventDefault();
        const export_dialog = new GNRExportDialog('Mouvement GNR', cur_list.get_filters());
        export_dialog.show();
    }
    
    // Ctrl + S pour soumettre tous les brouillons
    if (e.ctrlKey && e.key === 's' && cur_list && cur_list.doctype === 'Mouvement GNR') {
        e.preventDefault();
        gnr_compliance.utils.submit_pending_movements();
    }
});

// Hook pour personnaliser les actions de menu
frappe.ui.form.on('Mouvement GNR', {
    refresh: function(frm) {
        // Ajouter le bouton d'export dans le formulaire
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Générer Déclarations'), function() {
                const export_dialog = new GNRExportDialog('Mouvement GNR', {
                    'name': ['=', frm.doc.name]
                });
                export_dialog.show();
            }, __('Actions'));
        }
        
        // Ajouter un indicateur de catégorie client
        if (frm.doc.customer_category) {
            const color = frm.doc.customer_category === 'Agricole' ? 'green' : 'blue';
            frm.dashboard.set_headline(`
                <span class="indicator ${color}">
                    Client ${frm.doc.customer_category}
                    ${frm.doc.customer_category === 'Agricole' ? '(Taux réduit 3.86€/hL)' : '(Taux normal 24.81€/hL)'}
                </span>
            `);
        }
    }
});