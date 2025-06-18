// Améliorations pour Sales Invoice GNR
frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Ajouter des indicateurs GNR pour les factures validées
		if (frm.doc.docstatus === 1) {
			add_gnr_indicators(frm);
		}

		// Bouton pour analyser les articles GNR
		if (frm.doc.items && frm.doc.items.length > 0) {
			frm.add_custom_button(
				__("Analyser GNR"),
				function () {
					analyze_gnr_items(frm);
				},
				__("Actions")
			);
		}
	},

	onload: function (frm) {
		// Filtrer les articles GNR si nécessaire
		setup_gnr_item_filters(frm);
	},
});

function add_gnr_indicators(frm) {
	if (!frm.doc.items) return;

	let gnr_items = frm.doc.items.filter((item) => {
		// Logique simple pour détecter les articles GNR
		return (
			item.item_code &&
			(item.item_code.toLowerCase().includes("gnr") ||
				item.item_code.toLowerCase().includes("gazole") ||
				item.item_code.toLowerCase().includes("fioul") ||
				(item.item_name &&
					(item.item_name.toLowerCase().includes("gnr") ||
						item.item_name.toLowerCase().includes("gazole") ||
						item.item_name.toLowerCase().includes("fioul"))))
		);
	});

	if (gnr_items.length > 0) {
		frm.dashboard.add_indicator(__("Articles GNR: {0}", [gnr_items.length]), "orange");

		// Calculer la valeur totale GNR
		let total_gnr = gnr_items.reduce((sum, item) => sum + (item.amount || 0), 0);
		frm.dashboard.add_indicator(__("Montant GNR: {0}", [format_currency(total_gnr)]), "blue");
	}
}

function analyze_gnr_items(frm) {
	let gnr_items = [];

	frm.doc.items.forEach(function (item) {
		// Vérifier si l'article est potentiellement GNR
		if (is_potential_gnr_item(item)) {
			gnr_items.push({
				item_code: item.item_code,
				item_name: item.item_name,
				qty: item.qty,
				rate: item.rate,
				amount: item.amount,
			});
		}
	});

	if (gnr_items.length > 0) {
		// Afficher un dialog avec les articles GNR détectés
		let dialog = new frappe.ui.Dialog({
			title: __("Articles GNR Détectés"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "gnr_items_html",
				},
			],
		});

		let html =
			'<table class="table table-bordered"><thead><tr>' +
			"<th>Code Article</th><th>Nom</th><th>Qté</th><th>Prix</th><th>Montant</th>" +
			"</tr></thead><tbody>";

		gnr_items.forEach(function (item) {
			html += `<tr>
                <td>${item.item_code}</td>
                <td>${item.item_name}</td>
                <td>${item.qty}</td>
                <td>${format_currency(item.rate)}</td>
                <td>${format_currency(item.amount)}</td>
            </tr>`;
		});

		html += "</tbody></table>";
		dialog.fields_dict.gnr_items_html.$wrapper.html(html);
		dialog.show();
	} else {
		frappe.msgprint(__("Aucun article GNR détecté dans cette facture."));
	}
}

function is_potential_gnr_item(item) {
	if (!item.item_code && !item.item_name) return false;

	const gnr_keywords = ["gnr", "gazole", "fioul", "adblue", "combustible"];
	const item_text = (item.item_code + " " + (item.item_name || "")).toLowerCase();

	return gnr_keywords.some((keyword) => item_text.includes(keyword));
}

function setup_gnr_item_filters(frm) {
	// Configuration des filtres pour les articles GNR
	// À implémenter selon les besoins spécifiques
}
