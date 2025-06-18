// Améliorations pour Purchase Invoice GNR
frappe.ui.form.on("Purchase Invoice", {
	refresh: function (frm) {
		// Ajouter des indicateurs GNR pour les factures validées
		if (frm.doc.docstatus === 1) {
			add_gnr_purchase_indicators(frm);
		}

		// Bouton pour analyser les achats GNR
		if (frm.doc.items && frm.doc.items.length > 0) {
			frm.add_custom_button(
				__("Analyser Achats GNR"),
				function () {
					analyze_gnr_purchases(frm);
				},
				__("Actions")
			);
		}
	},

	onload: function (frm) {
		// Filtrer les articles GNR pour les achats
		setup_gnr_purchase_filters(frm);
	},
});

function add_gnr_purchase_indicators(frm) {
	if (!frm.doc.items) return;

	let gnr_items = frm.doc.items.filter((item) => {
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
		frm.dashboard.add_indicator(__("Achats GNR: {0}", [gnr_items.length]), "green");

		// Calculer la valeur totale des achats GNR
		let total_purchase_gnr = gnr_items.reduce((sum, item) => sum + (item.amount || 0), 0);
		frm.dashboard.add_indicator(
			__("Montant Achat GNR: {0}", [format_currency(total_purchase_gnr)]),
			"blue"
		);
	}
}

function analyze_gnr_purchases(frm) {
	let gnr_purchases = [];

	frm.doc.items.forEach(function (item) {
		if (is_potential_gnr_item(item)) {
			gnr_purchases.push({
				item_code: item.item_code,
				item_name: item.item_name,
				qty: item.qty,
				rate: item.rate,
				amount: item.amount,
				warehouse: item.warehouse,
			});
		}
	});

	if (gnr_purchases.length > 0) {
		let dialog = new frappe.ui.Dialog({
			title: __("Achats GNR Détectés"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "gnr_purchases_html",
				},
			],
		});

		let html =
			'<table class="table table-bordered"><thead><tr>' +
			"<th>Code Article</th><th>Nom</th><th>Qté</th><th>Prix</th><th>Montant</th><th>Entrepôt</th>" +
			"</tr></thead><tbody>";

		gnr_purchases.forEach(function (item) {
			html += `<tr>
                <td>${item.item_code}</td>
                <td>${item.item_name}</td>
                <td>${item.qty}</td>
                <td>${format_currency(item.rate)}</td>
                <td>${format_currency(item.amount)}</td>
                <td>${item.warehouse || ""}</td>
            </tr>`;
		});

		html += "</tbody></table>";
		dialog.fields_dict.gnr_purchases_html.$wrapper.html(html);
		dialog.show();
	} else {
		frappe.msgprint(__("Aucun achat GNR détecté dans cette facture."));
	}
}

function setup_gnr_purchase_filters(frm) {
	// Configuration des filtres pour les achats GNR
	// À implémenter selon les besoins spécifiques
}
