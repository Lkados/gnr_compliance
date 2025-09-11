// Version minimale sans boucle infinie pour Sales Invoice GNR
// Ne contient que l'essentiel sans event handlers problématiques

frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Seulement pour les documents soumis
		if (frm.doc.docstatus === 1) {
			// Ajouter un indicateur GNR simple
			check_gnr_movements_simple(frm);
		}
	}
});

function check_gnr_movements_simple(frm) {
	// Vérification simple sans triggers complexes
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Mouvement GNR",
			filters: {
				reference_document: "Sales Invoice",
				reference_name: frm.doc.name,
			},
			fields: ["name", "docstatus", "type_mouvement", "quantite"],
		},
		callback: function (r) {
			if (r.message && r.message.length > 0) {
				const active_movements = r.message.filter(m => m.docstatus === 1);
				if (active_movements.length > 0) {
					frm.dashboard.add_comment(
						`📋 ${active_movements.length} mouvement(s) GNR lié(s)`,
						"blue",
						true
					);
				}
			}
		},
	});
}

console.log("[GNR] Version minimale Sales Invoice chargée");