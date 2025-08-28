// gnr_compliance/public/js/gnr_management.js

// Fonctions pour la gestion des mouvements GNR
frappe.provide("gnr_compliance.utils");

gnr_compliance.utils = {
	// Exporter les déclarations GNR avec format officiel
	export_declarations: function() {
		const export_dialog = new GNRExportDialog('Mouvement GNR', {});
		export_dialog.show();
	},
	// Soumet tous les mouvements GNR en brouillon
	submit_pending_movements: function () {
		frappe.confirm(__("Soumettre tous les mouvements GNR en brouillon ?"), function () {
			frappe.show_alert({
				message: __("Soumission en cours..."),
				indicator: "blue",
			});

			frappe.call({
				method: "gnr_compliance.utils.gnr_utilities.submit_pending_gnr_movements",
				callback: function (r) {
					if (r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: "green",
						});

						// Afficher les détails
						gnr_compliance.utils.show_submission_results(r.message);
					} else {
						frappe.msgprint({
							title: __("Erreur"),
							message: r.message.error || "Erreur lors de la soumission",
							indicator: "red",
						});
					}
				},
			});
		});
	},

	// Affiche les résultats de soumission
	show_submission_results: function (results) {
		let message = `
            <div class="row">
                <div class="col-sm-6">
                    <div class="alert alert-success">
                        <strong>✅ Soumis:</strong> ${results.submitted_count}
                    </div>
                </div>
                <div class="col-sm-6">
                    <div class="alert alert-warning">
                        <strong>⚠️ Échecs:</strong> ${results.failed_count}
                    </div>
                </div>
            </div>
        `;

		if (results.failed_movements && results.failed_movements.length > 0) {
			message += "<hr><h5>Mouvements en échec:</h5><ul>";
			results.failed_movements.forEach(function (failure) {
				message += `<li><strong>${failure.name}:</strong> ${failure.reason}</li>`;
			});
			message += "</ul>";
		}

		frappe.msgprint({
			title: __("Résultats de la soumission"),
			message: message,
			indicator: "blue",
		});
	},

	// Affiche le résumé des mouvements GNR
	show_movements_summary: function () {
		let dialog = new frappe.ui.Dialog({
			title: __("Résumé des Mouvements GNR"),
			fields: [
				{
					fieldtype: "Date",
					fieldname: "from_date",
					label: __("Date de début"),
					default: frappe.datetime.month_start(),
				},
				{
					fieldtype: "Date",
					fieldname: "to_date",
					label: __("Date de fin"),
					default: frappe.datetime.month_end(),
				},
				{
					fieldtype: "HTML",
					fieldname: "summary_html",
				},
			],
			primary_action: function () {
				let values = dialog.get_values();
				gnr_compliance.utils.load_summary(values.from_date, values.to_date, dialog);
			},
			primary_action_label: __("Actualiser"),
		});

		// Charger le résumé initial
		gnr_compliance.utils.load_summary(
			frappe.datetime.month_start(),
			frappe.datetime.month_end(),
			dialog
		);

		dialog.show();
	},

	// Charge le résumé des mouvements
	load_summary: function (from_date, to_date, dialog) {
		frappe.call({
			method: "gnr_compliance.utils.gnr_utilities.get_gnr_movements_summary",
			args: {
				from_date: from_date,
				to_date: to_date,
			},
			callback: function (r) {
				if (r.message && !r.message.error) {
					let html = gnr_compliance.utils.build_summary_html(r.message);
					dialog.fields_dict.summary_html.$wrapper.html(html);
				} else {
					dialog.fields_dict.summary_html.$wrapper.html(
						'<div class="alert alert-danger">Erreur lors du chargement du résumé</div>'
					);
				}
			},
		});
	},

	// Construit le HTML du résumé
	build_summary_html: function (data) {
		let html = `
            <div class="gnr-summary">
                <div class="row">
                    <div class="col-sm-12">
                        <h5>Période: ${data.period.from} au ${data.period.to}</h5>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-sm-4">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-warning">${data.draft.count}</h3>
                                <p>Brouillons</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-sm-4">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-success">${data.submitted.count}</h3>
                                <p>Soumis</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-sm-4">
                        <div class="card">
                            <div class="card-body text-center">
                                <h3 class="text-danger">${data.cancelled.count}</h3>
                                <p>Annulés</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-3">
                    <div class="col-sm-6">
                        <div class="card">
                            <div class="card-body">
                                <h5>Quantité totale</h5>
                                <h3>${data.totals.quantity.toFixed(2)}</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-sm-6">
                        <div class="card">
                            <div class="card-body">
                                <h5>Taxe totale</h5>
                                <h3>${format_currency(data.totals.tax)}</h3>
                            </div>
                        </div>
                    </div>
                </div>
        `;

		// Détail par type de mouvement
		if (Object.keys(data.submitted.movements).length > 0) {
			html += `
                <div class="row mt-3">
                    <div class="col-sm-12">
                        <h5>Détail par type de mouvement (Soumis)</h5>
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>Type</th>
                                    <th>Nombre</th>
                                    <th>Quantité</th>
                                    <th>Taxe</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

			Object.keys(data.submitted.movements).forEach(function (type) {
				let movement = data.submitted.movements[type];
				html += `
                    <tr>
                        <td>${type}</td>
                        <td>${movement.count}</td>
                        <td>${movement.quantity.toFixed(2)}</td>
                        <td>${format_currency(movement.tax)}</td>
                    </tr>
                `;
			});

			html += "</tbody></table>";
		}

		html += "</div></div>";

		return html;
	},

	// Corrige les périodes manquantes
	fix_missing_periods: function () {
		frappe.confirm(__("Corriger les trimestres/semestres manquants ?"), function () {
			frappe.call({
				method: "gnr_compliance.utils.gnr_utilities.fix_missing_periods",
				callback: function (r) {
					if (r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: "green",
						});
					} else {
						frappe.msgprint({
							title: __("Erreur"),
							message: r.message.error,
							indicator: "red",
						});
					}
				},
			});
		});
	},

	// Nettoie les mouvements invalides
	cleanup_invalid: function () {
		frappe.confirm(
			__("Supprimer les mouvements GNR invalides (articles inexistants) ?"),
			function () {
				frappe.call({
					method: "gnr_compliance.utils.gnr_utilities.cleanup_invalid_movements",
					callback: function (r) {
						if (r.message.success) {
							frappe.show_alert({
								message: r.message.message,
								indicator: "green",
							});
						} else {
							frappe.msgprint({
								title: __("Erreur"),
								message: r.message.error,
								indicator: "red",
							});
						}
					},
				});
			}
		);
	},
};

// Amélioration du formulaire Mouvement GNR
frappe.ui.form.on("Mouvement GNR", {
	refresh: function (frm) {
		// Ajouter des indicateurs de statut
		if (frm.doc.docstatus === 0) {
			frm.dashboard.add_indicator(__("Brouillon"), "orange");
		} else if (frm.doc.docstatus === 1) {
			frm.dashboard.add_indicator(__("Soumis"), "green");
		}

		// Bouton pour soumettre plusieurs mouvements
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Soumettre tous les brouillons"),
				function () {
					gnr_compliance.utils.submit_pending_movements();
				},
				__("Actions")
			);
		}

		// Afficher les informations de taxe
		if (frm.doc.montant_taxe_gnr) {
			frm.dashboard.add_indicator(
				__("Taxe GNR: {0}", [format_currency(frm.doc.montant_taxe_gnr)]),
				"blue"
			);
		}
	},

	code_produit: function (frm) {
		// Auto-remplir les données GNR de l'article
		if (frm.doc.code_produit) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Item",
					fieldname: ["gnr_tracked_category", "gnr_tax_rate"],
					filters: { name: frm.doc.code_produit },
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value("categorie_gnr", "GNR");
						frm.set_value("taux_gnr", r.message.gnr_tax_rate);

						// Recalculer la taxe
						if (frm.doc.quantite) {
							frm.trigger("quantite");
						}
					}
				},
			});
		}
	},

	quantite: function (frm) {
		// Recalculer automatiquement la taxe
		if (frm.doc.quantite && frm.doc.taux_gnr) {
			let tax_amount = frm.doc.quantite * frm.doc.taux_gnr;
			frm.set_value("montant_taxe_gnr", tax_amount);
		}
	},

	taux_gnr: function (frm) {
		// Recalculer automatiquement la taxe
		if (frm.doc.quantite && frm.doc.taux_gnr) {
			let tax_amount = frm.doc.quantite * frm.doc.taux_gnr;
			frm.set_value("montant_taxe_gnr", tax_amount);
		}
	},
});
