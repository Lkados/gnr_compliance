frappe.ui.form.on("Mouvement GNR", {
	refresh: function(frm) {
		// Ajouter bouton de suppression pour les mouvements GNR
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Supprimer ce mouvement'), function() {
				frappe.confirm(
					'Êtes-vous sûr de vouloir supprimer ce mouvement GNR ? Cette action annulera et supprimera définitivement ce mouvement.',
					function() {
						frappe.call({
							method: 'gnr_compliance.integrations.stock.delete_gnr_movement',
							args: {
								movement_name: frm.doc.name
							},
							callback: function(r) {
								if (r.message && r.message.success) {
									frappe.msgprint({
										title: 'Succès',
										message: 'Le mouvement GNR a été supprimé avec succès',
										indicator: 'green'
									});
									frappe.set_route('List', 'Mouvement GNR');
								} else {
									frappe.msgprint({
										title: 'Erreur',
										message: r.message.error || 'Erreur lors de la suppression',
										indicator: 'red'
									});
								}
							}
						});
					}
				);
			}, __('Actions'));
		} else if (frm.doc.docstatus === 0) {
			// Pour les brouillons, permettre suppression directe
			frm.add_custom_button(__('Supprimer ce brouillon'), function() {
				frappe.confirm(
					'Supprimer ce brouillon de mouvement GNR ?',
					function() {
						frappe.model.delete_doc(frm.doctype, frm.doc.name, function() {
							frappe.set_route('List', 'Mouvement GNR');
						});
					}
				);
			}, __('Actions'));
		}
	},

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
