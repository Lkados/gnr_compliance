// gnr_compliance/doctype/declaration_periode_gnr/declaration_periode_gnr.js

frappe.ui.form.on("Declaration Periode GNR", {
	refresh: function (frm) {
		// Ajouter des indicateurs de statut
		add_status_indicators(frm);

		// Boutons d'actions personnalisés
		add_custom_buttons(frm);

		// Afficher les informations de conformité
		show_compliance_info(frm);

		// Auto-calculer les dates si vide
		if (!frm.doc.date_debut || !frm.doc.date_fin) {
			calculate_period_dates(frm);
		}
	},

	type_periode: function (frm) {
		// Recalculer les dates quand le type de période change
		calculate_period_dates(frm);
		update_periode_options(frm);
	},

	periode: function (frm) {
		// Recalculer les dates quand la période change
		calculate_period_dates(frm);
	},

	annee: function (frm) {
		// Recalculer les dates quand l'année change
		calculate_period_dates(frm);
	},

	date_debut: function (frm) {
		// Valider que date_fin > date_debut
		if (frm.doc.date_debut && frm.doc.date_fin) {
			if (frappe.datetime.get_diff(frm.doc.date_fin, frm.doc.date_debut) < 0) {
				frappe.msgprint(__("La date de fin doit être postérieure à la date de début"));
				frm.set_value("date_fin", "");
			}
		}
	},

	inclure_details_clients: function (frm) {
		// Alerter si semestriel sans détails clients
		if (frm.doc.type_periode === "Semestriel" && !frm.doc.inclure_details_clients) {
			frappe.msgprint({
				title: __("Attention Réglementaire"),
				message: __(
					"La déclaration semestrielle DOIT inclure les détails clients selon la réglementation française."
				),
				indicator: "orange",
			});
		}
	},
});

// Gestion des tables enfants
frappe.ui.form.on("Type Mouvement Filter", {
	types_mouvement_add: function (frm, cdt, cdn) {
		// Pré-remplir avec les types communs
		let row = locals[cdt][cdn];
		if (!row.type_mouvement) {
			// Suggérer le premier type non utilisé
			let types_utilises = frm.doc.types_mouvement.map((t) => t.type_mouvement);
			let types_disponibles = ["Vente", "Achat", "Stock", "Transfert", "Entrée", "Sortie"];
			let premier_libre = types_disponibles.find((type) => !types_utilises.includes(type));
			if (premier_libre) {
				frappe.model.set_value(cdt, cdn, "type_mouvement", premier_libre);
			}
		}
	},
});

frappe.ui.form.on("Produit GNR Filter", {
	code_produit: function (frm, cdt, cdn) {
		// Auto-remplir les infos du produit
		let row = locals[cdt][cdn];
		if (row.code_produit) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Item",
					fieldname: ["item_name", "gnr_tracked_category"],
					filters: { name: row.code_produit },
				},
				callback: function (r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, "nom_produit", r.message.item_name);
						frappe.model.set_value(
							cdt,
							cdn,
							"categorie_gnr",
							r.message.gnr_tracked_category
						);
					}
				},
			});
		}
	},
});

// === FONCTIONS UTILITAIRES ===

function add_status_indicators(frm) {
	// Indicateur de période
	if (frm.doc.type_periode && frm.doc.periode && frm.doc.annee) {
		let periode_text = `${frm.doc.type_periode} ${frm.doc.periode}/${frm.doc.annee}`;
		frm.dashboard.add_indicator(__("Période: {0}", [periode_text]), "blue");
	}

	// Indicateur de statut
	if (frm.doc.statut) {
		let color = {
			Brouillon: "orange",
			"En cours": "yellow",
			Soumise: "blue",
			Validée: "green",
			Transmise: "purple",
		}[frm.doc.statut];
		frm.dashboard.add_indicator(__("Statut: {0}", [frm.doc.statut]), color);
	}

	// Indicateurs de données
	if (frm.doc.total_ventes) {
		frm.dashboard.add_indicator(
			__("Ventes: {0} L", [format_number(frm.doc.total_ventes)]),
			"green"
		);
	}

	if (frm.doc.total_taxe_gnr) {
		frm.dashboard.add_indicator(
			__("Taxe GNR: {0}", [format_currency(frm.doc.total_taxe_gnr)]),
			"red"
		);
	}

	if (frm.doc.nb_clients) {
		frm.dashboard.add_indicator(__("Clients: {0}", [frm.doc.nb_clients]), "purple");
	}
}

function add_custom_buttons(frm) {
	if (frm.doc.docstatus === 0) {
		// Bouton pour charger automatiquement les produits GNR
		frm.add_custom_button(
			__("Charger Produits GNR"),
			function () {
				load_gnr_products(frm);
			},
			__("Actions")
		);

		// Bouton pour charger les types de mouvement standard
		frm.add_custom_button(
			__("Types Standard"),
			function () {
				load_standard_movement_types(frm);
			},
			__("Actions")
		);

		// Bouton recalcul
		frm.add_custom_button(
			__("🔄 Recalculer"),
			function () {
				recalculate_data(frm);
			},
			__("Actions")
		).addClass("btn-warning");
	}

	if (frm.doc.docstatus === 1) {
		// Bouton export Excel
		frm.add_custom_button(
			__("📊 Export Excel"),
			function () {
				generate_excel_export(frm);
			},
			__("Exports")
		).addClass("btn-primary");

		// Bouton vérification conformité
		frm.add_custom_button(
			__("✅ Vérifier Conformité"),
			function () {
				check_regulatory_compliance(frm);
			},
			__("Actions")
		);
	}

	// Bouton prévisualisation toujours disponible
	frm.add_custom_button(__("👁 Prévisualiser"), function () {
		show_preview_dialog(frm);
	});
}

function calculate_period_dates(frm) {
	if (!frm.doc.type_periode || !frm.doc.periode || !frm.doc.annee) {
		return;
	}

	let dates = get_period_dates(frm.doc.type_periode, frm.doc.periode, frm.doc.annee);

	if (dates) {
		frm.set_value("date_debut", dates.debut);
		frm.set_value("date_fin", dates.fin);
	}
}

function get_period_dates(type_periode, periode, annee) {
	let debut, fin;

	if (type_periode === "Mensuel") {
		let mois = parseInt(periode);
		if (mois >= 1 && mois <= 12) {
			debut = `${annee}-${mois.toString().padStart(2, "0")}-01`;
			// Dernier jour du mois
			let dernierJour = new Date(annee, mois, 0).getDate();
			fin = `${annee}-${mois.toString().padStart(2, "0")}-${dernierJour}`;
		}
	} else if (type_periode === "Trimestriel") {
		let trimestre = parseInt(periode.replace("T", ""));
		if (trimestre >= 1 && trimestre <= 4) {
			let mois_debut = (trimestre - 1) * 3 + 1;
			let mois_fin = trimestre * 3;

			debut = `${annee}-${mois_debut.toString().padStart(2, "0")}-01`;

			// Dernier jour du trimestre
			let dernierJour = new Date(annee, mois_fin, 0).getDate();
			fin = `${annee}-${mois_fin.toString().padStart(2, "0")}-${dernierJour}`;
		}
	} else if (type_periode === "Semestriel") {
		let semestre = parseInt(periode.replace("S", ""));
		if (semestre === 1) {
			debut = `${annee}-01-01`;
			fin = `${annee}-06-30`;
		} else if (semestre === 2) {
			debut = `${annee}-07-01`;
			fin = `${annee}-12-31`;
		}
	} else if (type_periode === "Annuel") {
		debut = `${annee}-01-01`;
		fin = `${annee}-12-31`;
	}

	return debut && fin ? { debut, fin } : null;
}

function update_periode_options(frm) {
	// Mettre à jour les options de période selon le type
	let options = [];

	if (frm.doc.type_periode === "Mensuel") {
		options = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"];
	} else if (frm.doc.type_periode === "Trimestriel") {
		options = ["T1", "T2", "T3", "T4"];
	} else if (frm.doc.type_periode === "Semestriel") {
		options = ["S1", "S2"];
	} else if (frm.doc.type_periode === "Annuel") {
		options = ["ANNEE"];
	}

	// Mise à jour du champ période (si possible)
	if (options.length > 0 && !options.includes(frm.doc.periode)) {
		frm.set_value("periode", "");
	}
}

function load_gnr_products(frm) {
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Item",
			filters: { is_gnr_tracked: 1, disabled: 0 },
			fields: ["name", "item_name", "gnr_tracked_category"],
			order_by: "gnr_tracked_category, item_name",
		},
		callback: function (r) {
			if (r.message && r.message.length > 0) {
				// Vider la table actuelle
				frm.clear_table("produits_inclus");

				// Ajouter tous les produits GNR
				r.message.forEach(function (item) {
					let row = frm.add_child("produits_inclus");
					row.code_produit = item.name;
					row.nom_produit = item.item_name;
					row.categorie_gnr = item.gnr_tracked_category;
					row.inclus = 1;
				});

				frm.refresh_field("produits_inclus");
				frappe.show_alert({
					message: __("{0} produits GNR chargés", [r.message.length]),
					indicator: "green",
				});
			} else {
				frappe.msgprint(__("Aucun produit GNR trouvé"));
			}
		},
	});
}

function load_standard_movement_types(frm) {
	// Types de mouvement standard selon la réglementation
	let types_standard = [
		{ type: "Vente", description: "Ventes aux clients" },
		{ type: "Achat", description: "Achats fournisseurs" },
		{ type: "Entrée", description: "Entrées en stock" },
		{ type: "Sortie", description: "Sorties de stock" },
	];

	// Vider la table
	frm.clear_table("types_mouvement");

	// Ajouter les types standard
	types_standard.forEach(function (type) {
		let row = frm.add_child("types_mouvement");
		row.type_mouvement = type.type;
		row.description = type.description;
		row.inclus = 1;
	});

	frm.refresh_field("types_mouvement");
	frappe.show_alert({
		message: __("Types de mouvement standard chargés"),
		indicator: "green",
	});
}

function recalculate_data(frm) {
	frappe.show_alert({
		message: __("Recalcul en cours..."),
		indicator: "blue",
	});

	// Sauvegarder pour déclencher le recalcul
	frm.save().then(() => {
		frappe.show_alert({
			message: __("Données recalculées avec succès"),
			indicator: "green",
		});
	});
}

function generate_excel_export(frm) {
	if (frm.doc.docstatus !== 1) {
		frappe.msgprint(__("Le document doit être soumis pour générer l'export"));
		return;
	}

	frappe.show_progress(__("Export en cours..."), 50, __("Génération du fichier Excel"));

	frm.call("generer_export_excel").then((r) => {
		frappe.hide_progress();

		if (r.message && r.message.file_url) {
			frappe.show_alert({
				message: __("Export généré : {0}", [r.message.file_name]),
				indicator: "green",
			});

			// Ouvrir le fichier
			window.open(r.message.file_url);
		} else {
			frappe.msgprint(__("Erreur lors de la génération de l'export"));
		}
	});
}

function check_regulatory_compliance(frm) {
	// Vérifier la conformité réglementaire
	try {
		let donnees = JSON.parse(frm.doc.donnees_detaillees || "{}");
		let conformite = donnees.conformite_reglementaire || {};

		let message = `
            <h5>🔍 Vérification Conformité Réglementaire</h5>
            
            <div class="alert ${
				conformite.statut === "conforme" ? "alert-success" : "alert-warning"
			}">
                <strong>Statut :</strong> ${conformite.statut?.toUpperCase() || "INCONNU"}
            </div>
        `;

		if (conformite.alertes && conformite.alertes.length > 0) {
			message += `
                <h6>⚠️ Alertes :</h6>
                <ul>
                    ${conformite.alertes.map((alerte) => `<li>${alerte}</li>`).join("")}
                </ul>
            `;
		}

		if (conformite.recommandations && conformite.recommandations.length > 0) {
			message += `
                <h6>💡 Recommandations :</h6>
                <ul>
                    ${conformite.recommandations.map((reco) => `<li>${reco}</li>`).join("")}
                </ul>
            `;
		}

		if (!conformite.alertes?.length && !conformite.recommandations?.length) {
			message += `
                <div class="alert alert-success">
                    ✅ Aucun problème de conformité détecté
                </div>
            `;
		}

		frappe.msgprint({
			title: __("Conformité Réglementaire"),
			message: message,
			indicator: conformite.statut === "conforme" ? "green" : "orange",
		});
	} catch (e) {
		frappe.msgprint(__("Erreur lors de la vérification de conformité"));
	}
}

function show_compliance_info(frm) {
	// Afficher des informations de conformité dans le dashboard
	if (frm.doc.type_periode === "Semestriel" && !frm.doc.inclure_details_clients) {
		frm.dashboard.add_comment(
			"⚠️ OBLIGATOIRE : Déclaration semestrielle doit inclure les détails clients",
			"red",
			true
		);
	}

	if (frm.doc.total_ventes > 10000) {
		frm.dashboard.add_comment(
			"📋 Volume important de ventes - Vérifiez les obligations déclaratives spéciales",
			"orange",
			true
		);
	}
}

function show_preview_dialog(frm) {
	// Dialog de prévisualisation des données
	let dialog = new frappe.ui.Dialog({
		title: __("Prévisualisation Déclaration"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "preview_html",
			},
		],
	});

	// Construire le HTML de prévisualisation
	let html = build_preview_html(frm);
	dialog.fields_dict.preview_html.$wrapper.html(html);

	dialog.show();
}

function build_preview_html(frm) {
	return `
        <div class="preview-container">
            <h4>${frm.doc.type_periode} ${frm.doc.periode}/${frm.doc.annee}</h4>
            
            <div class="row">
                <div class="col-sm-6">
                    <div class="card">
                        <div class="card-body">
                            <h6>📊 Résumé des Volumes</h6>
                            <table class="table table-sm">
                                <tr><td>Stock début</td><td>${format_number(
									frm.doc.stock_debut_periode || 0
								)} L</td></tr>
                                <tr><td>Total entrées</td><td>${format_number(
									frm.doc.total_entrees || 0
								)} L</td></tr>
                                <tr><td>Total sorties</td><td>${format_number(
									frm.doc.total_sorties || 0
								)} L</td></tr>
                                <tr><td>Stock fin</td><td>${format_number(
									frm.doc.stock_fin_periode || 0
								)} L</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
                
                <div class="col-sm-6">
                    <div class="card">
                        <div class="card-body">
                            <h6>💰 Résumé Financier</h6>
                            <table class="table table-sm">
                                <tr><td>Total ventes</td><td>${format_number(
									frm.doc.total_ventes || 0
								)} L</td></tr>
                                <tr><td>Taxe GNR</td><td>${format_currency(
									frm.doc.total_taxe_gnr || 0
								)}</td></tr>
                                <tr><td>Nb clients</td><td>${frm.doc.nb_clients || 0}</td></tr>
                                <tr><td>Statut</td><td><span class="indicator-pill ${
									frm.doc.statut === "Validée" ? "green" : "orange"
								}">${frm.doc.statut}</span></td></tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-sm-12">
                    <div class="card">
                        <div class="card-body">
                            <h6>🔧 Configuration</h6>
                            <p><strong>Types de mouvement :</strong> ${(
								frm.doc.types_mouvement || []
							)
								.filter((t) => t.inclus)
								.map((t) => t.type_mouvement)
								.join(", ")}</p>
                            <p><strong>Produits :</strong> ${
								(frm.doc.produits_inclus || []).length
							} produit(s) sélectionné(s)</p>
                            <p><strong>Détails clients :</strong> ${
								frm.doc.inclure_details_clients ? "✅ Inclus" : "❌ Non inclus"
							}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <style>
        .preview-container { padding: 15px; }
        .preview-container .card { margin-bottom: 10px; }
        .preview-container .table td { padding: 5px 8px; border: none; }
        .preview-container .table td:first-child { font-weight: 500; }
        .preview-container .table td:last-child { text-align: right; }
        </style>
    `;
}
