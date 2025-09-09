// Améliorations pour Stock Entry GNR
frappe.ui.form.on("Stock Entry", {
	refresh: function (frm) {
		// Ajouter des indicateurs GNR pour les mouvements validés
		if (frm.doc.docstatus === 1) {
			add_gnr_stock_indicators(frm);
		}

		// Bouton pour analyser les mouvements GNR
		if (frm.doc.items && frm.doc.items.length > 0) {
			frm.add_custom_button(
				__("Analyser Stock GNR"),
				function () {
					analyze_gnr_stock_movements(frm);
				},
				__("Actions")
			);
		}
	},

	stock_entry_type: function (frm) {
		// Activer la détection GNR pour TOUS les types de mouvements
		// Plus de restriction sur des types spécifiques
		enable_gnr_tracking(frm);
	},
});

frappe.ui.form.on("Stock Entry Detail", {
	item_code: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		// Vérifier si l'article sélectionné est GNR
		if (row.item_code && is_potential_gnr_item(row)) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Item",
					fieldname: ["is_gnr_tracked", "gnr_tracked_category"],
					filters: { name: row.item_code },
				},
				callback: function (r) {
					if (r.message && r.message.is_gnr_tracked) {
						frappe.show_alert({
							message: __("Article GNR détecté"),
							indicator: "orange",
						});
					}
				},
			});
		}
	},
});

function add_gnr_stock_indicators(frm) {
	if (!frm.doc.items) return;

	let gnr_items = frm.doc.items.filter((item) => {
		return (
			item.item_code &&
			(item.item_code.toLowerCase().includes("gnr") ||
				item.item_code.toLowerCase().includes("gazole") ||
				(item.item_name &&
					(item.item_name.toLowerCase().includes("gnr") ||
						item.item_name.toLowerCase().includes("gazole"))))
		);
	});

	if (gnr_items.length > 0) {
		frm.dashboard.add_indicator(__("Mouvements GNR: {0}", [gnr_items.length]), "purple");

		// Calculer la quantité totale des mouvements GNR
		let total_qty = gnr_items.reduce((sum, item) => sum + (item.qty || 0), 0);
		frm.dashboard.add_indicator(__("Quantité GNR: {0}", [total_qty]), "blue");
	}
}

function analyze_gnr_stock_movements(frm) {
	let gnr_movements = [];

	frm.doc.items.forEach(function (item) {
		if (is_potential_gnr_item(item)) {
			gnr_movements.push({
				item_code: item.item_code,
				item_name: item.item_name,
				qty: item.qty,
				uom: item.uom,
				s_warehouse: item.s_warehouse,
				t_warehouse: item.t_warehouse,
				basic_rate: item.basic_rate,
			});
		}
	});

	if (gnr_movements.length > 0) {
		let dialog = new frappe.ui.Dialog({
			title: __("Mouvements Stock GNR"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "gnr_movements_html",
				},
			],
		});

		let html =
			'<table class="table table-bordered"><thead><tr>' +
			"<th>Article</th><th>Nom</th><th>Qté</th><th>UDM</th><th>De</th><th>Vers</th>" +
			"</tr></thead><tbody>";

		gnr_movements.forEach(function (item) {
			html += `<tr>
                <td>${item.item_code}</td>
                <td>${item.item_name || ""}</td>
                <td>${item.qty}</td>
                <td>${item.uom || ""}</td>
                <td>${item.s_warehouse || ""}</td>
                <td>${item.t_warehouse || ""}</td>
            </tr>`;
		});

		html += "</tbody></table>";
		dialog.fields_dict.gnr_movements_html.$wrapper.html(html);
		dialog.show();
	} else {
		frappe.msgprint(__("Aucun mouvement GNR détecté."));
	}
}

function is_potential_gnr_item(item) {
	// Détection basée uniquement sur les termes GNR/Gazole
	return (
		item.item_code &&
		(item.item_code.toLowerCase().includes("gnr") ||
			item.item_code.toLowerCase().includes("gazole") ||
			(item.item_name &&
				(item.item_name.toLowerCase().includes("gnr") ||
					item.item_name.toLowerCase().includes("gazole"))))
	);
}

function enable_gnr_tracking(frm) {
	// Activer le tracking GNR pour ce mouvement de stock
	if (!frm.doc.gnr_categories_processed) {
		frm.set_value("gnr_categories_processed", 1);
	}
}
