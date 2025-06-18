// Amélioration du formulaire GNR Category Settings
frappe.ui.form.on("GNR Category Settings", {
	refresh: function (frm) {
		// Bouton pour tester toutes les règles
		frm.add_custom_button(__("Tester toutes les Règles"), function () {
			test_all_category_rules(frm);
		});

		// Bouton pour appliquer aux articles existants
		frm.add_custom_button(__("Appliquer aux Articles Existants"), function () {
			apply_to_existing_items(frm);
		});

		// Afficher le nombre de catégories actives
		if (frm.doc.category_rules) {
			let active_count = frm.doc.category_rules.filter((r) => r.is_active).length;
			frm.dashboard.add_indicator(
				__("Catégories Actives: {0}", [active_count]),
				active_count > 0 ? "green" : "red"
			);
		}
	},
});

// Ajouter les fonctions de test et d'application
function test_all_category_rules(frm) {
	let dialog = new frappe.ui.Dialog({
		title: __("Tester les Règles de Catégories"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "test_item",
				label: __("Article à Tester"),
				options: "Item",
				reqd: 1,
			},
		],
		primary_action: function () {
			let values = dialog.get_values();

			frm.call("test_category_match", {
				item_code: values.test_item,
			}).then((r) => {
				if (r.message.matched) {
					frappe.msgprint({
						title: __("Test Réussi"),
						message: __("Article correspond à la catégorie: {0}", [
							r.message.category,
						]),
						indicator: "green",
					});
				} else {
					frappe.msgprint({
						title: __("Aucune Correspondance"),
						message: __("L'article ne correspond à aucune règle active."),
						indicator: "orange",
					});
				}
			});

			dialog.hide();
		},
		primary_action_label: __("Tester"),
	});

	dialog.show();
}

function apply_to_existing_items(frm) {
	frappe.confirm(
		__("Appliquer les règles de catégories à tous les articles existants?"),
		function () {
			frappe.call({
				method: "gnr_compliance.utils.category_detector.apply_categories_to_existing_items",
				callback: function (r) {
					if (r.message) {
						frappe.msgprint(
							__("Traitement terminé: {0} articles mis à jour", [
								r.message.updated_count,
							])
						);
					}
				},
			});
		}
	);
}
