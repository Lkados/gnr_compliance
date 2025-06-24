// gnr_compliance/gnr_compliance/doctype/declaration_periode_gnr/declaration_periode_gnr.js

frappe.ui.form.on("Declaration Periode GNR", {
	refresh: function (frm) {
		// Ajouter boutons d'action simples
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button("📊 Générer", function () {
				generer_declaration(frm);
			}).addClass("btn-primary");
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("📄 Export Excel", function () {
				export_excel(frm);
			}).addClass("btn-success");
		}

		// Afficher résumé si soumis
		if (frm.doc.docstatus === 1) {
			afficher_resume(frm);
		}
	},

	type_periode: function (frm) {
		// Mettre à jour les options de période selon le type
		mettre_a_jour_periodes(frm);
		calculer_dates(frm);
	},

	periode: function (frm) {
		calculer_dates(frm);
	},

	annee: function (frm) {
		calculer_dates(frm);
	},
});

function mettre_a_jour_periodes(frm) {
	let options = [];

	if (frm.doc.type_periode === "Trimestriel") {
		options = ["T1", "T2", "T3", "T4"];
	} else if (frm.doc.type_periode === "Semestriel") {
		options = ["S1", "S2"];
	} else if (frm.doc.type_periode === "Annuel") {
		options = ["ANNEE"];
	}

	// Mettre à jour les options du champ période
	frm.set_df_property("periode", "options", options.join("\n"));

	// Reset la période si elle n'est plus valide
	if (!options.includes(frm.doc.periode)) {
		frm.set_value("periode", "");
	}
}

function calculer_dates(frm) {
	if (!frm.doc.type_periode || !frm.doc.periode || !frm.doc.annee) {
		return;
	}

	let dates = obtenir_dates_periode(frm.doc.type_periode, frm.doc.periode, frm.doc.annee);

	if (dates) {
		frm.set_value("date_debut", dates.debut);
		frm.set_value("date_fin", dates.fin);
	}
}

function obtenir_dates_periode(type, periode, annee) {
	if (type === "Trimestriel") {
		let trimestre = parseInt(periode.replace("T", ""));
		let mois_debut = (trimestre - 1) * 3 + 1;
		let mois_fin = trimestre * 3;

		return {
			debut: `${annee}-${mois_debut.toString().padStart(2, "0")}-01`,
			fin: `${annee}-${mois_fin.toString().padStart(2, "0")}-${new Date(
				annee,
				mois_fin,
				0
			).getDate()}`,
		};
	} else if (type === "Semestriel") {
		let semestre = parseInt(periode.replace("S", ""));
		if (semestre === 1) {
			return { debut: `${annee}-01-01`, fin: `${annee}-06-30` };
		} else {
			return { debut: `${annee}-07-01`, fin: `${annee}-12-31` };
		}
	} else if (type === "Annuel") {
		return { debut: `${annee}-01-01`, fin: `${annee}-12-31` };
	}
	return null;
}

function generer_declaration(frm) {
	if (!frm.doc.date_debut || !frm.doc.date_fin) {
		frappe.msgprint("Veuillez sélectionner une période valide");
		return;
	}

	frappe.show_progress("Génération...", 50, "Calcul des données GNR");

	// Sauvegarder pour déclencher les calculs
	frm.save().then(() => {
		frappe.hide_progress();
		frappe.show_alert({
			message: "Déclaration générée avec succès",
			indicator: "green",
		});
	});
}

function export_excel(frm) {
	frappe.show_progress("Export...", 70, "Génération du fichier Excel");

	frm.call("generer_export_excel").then((r) => {
		frappe.hide_progress();
		if (r.message && r.message.file_url) {
			window.open(r.message.file_url);
		}
	});
}

function afficher_resume(frm) {
	// Afficher un résumé visuel des données
	if (frm.doc.total_ventes) {
		frm.dashboard.add_indicator(`Ventes: ${format_number(frm.doc.total_ventes)} L`, "blue");
	}

	if (frm.doc.total_taxe_gnr) {
		frm.dashboard.add_indicator(`Taxe: ${format_currency(frm.doc.total_taxe_gnr)}`, "green");
	}

	if (frm.doc.nb_clients) {
		frm.dashboard.add_indicator(`Clients: ${frm.doc.nb_clients}`, "orange");
	}
}
