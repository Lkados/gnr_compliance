frappe.ui.form.on("Mouvement GNR", {
	code_produit: function (frm) {
		if (frm.doc.code_produit) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Item",
					fieldname: "gnr_tax_rate",
					filters: { name: frm.doc.code_produit },
				},
				callback: function (r) {
					if (r.message && r.message.gnr_tax_rate) {
						frm.set_value("taux_gnr", r.message.gnr_tax_rate);
						calculer_montant_taxe(frm);
					}
				},
			});
		}
	},

	quantite: function (frm) {
		calculer_montant_taxe(frm);
	},

	taux_gnr: function (frm) {
		calculer_montant_taxe(frm);
	},
});

function calculer_montant_taxe(frm) {
	if (frm.doc.quantite && frm.doc.taux_gnr) {
		let montant = frm.doc.quantite * frm.doc.taux_gnr;
		frm.set_value("montant_taxe_gnr", montant);

		frappe.show_alert({
			message: `${frm.doc.quantite}L × ${frm.doc.taux_gnr}€/L = ${montant.toFixed(2)}€`,
			indicator: "green",
		});
	}
}
