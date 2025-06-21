// ==========================================
// FICHIER: public/js/sales_invoice_gnr.js
// BOUTON SIMPLE pour annuler factures avec mouvements GNR
// ==========================================

frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Ajouter bouton d'annulation GNR si le document est soumis
		if (frm.doc.docstatus === 1) {
			// Vérifier s'il y a des mouvements GNR liés
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Mouvement GNR",
					filters: {
						reference_document: "Sales Invoice",
						reference_name: frm.doc.name,
						docstatus: 1,
					},
					fields: ["name", "type_mouvement", "quantite"],
				},
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						// Il y a des mouvements GNR, ajouter le bouton
						frm.add_custom_button(
							__("🔄 Annuler avec GNR"),
							function () {
								show_gnr_cancel_dialog(frm, r.message);
							},
							__("Actions")
						).addClass("btn-warning");

						// Ajouter info dans le dashboard
						frm.dashboard.add_comment(
							`⚠️ ${r.message.length} mouvement(s) GNR lié(s) à cette facture`,
							"orange",
							true
						);
					}
				},
			});
		}
	},
});

function show_gnr_cancel_dialog(frm, gnr_movements) {
	const movements_list = gnr_movements
		.map(
			(m) =>
				`• <strong>${m.name}</strong> - ${m.type_mouvement || "N/A"} (${
					m.quantite || 0
				} L)`
		)
		.join("<br>");

	const dialog = new frappe.ui.Dialog({
		title: __("🔄 Annulation Facture + GNR"),
		fields: [
			{
				fieldname: "info",
				fieldtype: "HTML",
				options: `
                    <div class="alert alert-info">
                        <h6><i class="fa fa-info-circle"></i> Mouvements GNR détectés</h6>
                        <p>Cette facture est liée à <strong>${gnr_movements.length} mouvement(s) GNR</strong> :</p>
                        <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                            ${movements_list}
                        </div>
                    </div>
                `,
			},
			{
				fieldname: "section_break",
				fieldtype: "Section Break",
			},
			{
				fieldname: "action_type",
				label: "Action à effectuer",
				fieldtype: "Select",
				options: [
					"",
					"🔄 Annuler automatiquement tout (mouvements + facture)",
					"📋 Annuler seulement les mouvements GNR",
					"❌ Annulation normale (vous gérez les mouvements manuellement)",
				],
				reqd: 1,
			},
			{
				fieldname: "column_break",
				fieldtype: "Column Break",
			},
			{
				fieldname: "confirm_action",
				fieldtype: "Check",
				label: "✅ Je confirme cette action",
				default: 0,
			},
		],
		size: "large",
		primary_action_label: __("Exécuter"),
		primary_action: function (data) {
			if (!data.confirm_action) {
				frappe.msgprint({
					title: __("Confirmation requise"),
					message: __("Veuillez cocher la case de confirmation"),
					indicator: "red",
				});
				return;
			}

			dialog.hide();
			execute_gnr_action(frm, data.action_type);
		},
		secondary_action_label: __("Fermer"),
		secondary_action: function () {
			dialog.hide();
		},
	});

	dialog.show();
}

function execute_gnr_action(frm, action_type) {
	if (action_type.includes("Annuler automatiquement tout")) {
		// Annulation complète
		frappe.show_progress(__("Annulation"), 0, __("Début du processus..."));

		frappe.call({
			method: "gnr_compliance.utils.gnr_cancel_helper.cancel_invoice_with_gnr",
			args: {
				doctype: "Sales Invoice",
				name: frm.doc.name,
			},
			callback: function (r) {
				frappe.hide_progress();

				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __("✅ " + r.message.message),
						indicator: "green",
					});
					setTimeout(() => frm.reload_doc(), 1000);
				} else {
					frappe.msgprint({
						title: __("Erreur"),
						message: r.message ? r.message.message : __("Erreur lors de l'annulation"),
						indicator: "red",
					});
				}
			},
		});
	} else if (action_type.includes("Annuler seulement les mouvements")) {
		// Annulation des mouvements seulement
		frappe.show_progress(__("Annulation GNR"), 0, __("Annulation des mouvements..."));

		frappe.call({
			method: "gnr_compliance.utils.gnr_cancel_helper.cancel_related_gnr_movements",
			args: {
				doctype: "Sales Invoice",
				name: frm.doc.name,
			},
			callback: function (r) {
				frappe.hide_progress();

				if (r.message !== undefined) {
					frappe.show_alert({
						message: __(`✅ ${r.message} mouvement(s) GNR annulé(s)`),
						indicator: "green",
					});

					frappe.msgprint({
						title: __("Mouvements annulés"),
						message: __(
							"Les mouvements GNR ont été annulés. Vous pouvez maintenant annuler la facture normalement."
						),
						indicator: "blue",
					});
				} else {
					frappe.msgprint({
						title: __("Erreur"),
						message: __("Erreur lors de l'annulation des mouvements"),
						indicator: "red",
					});
				}
			},
		});
	} else {
		// Annulation normale - juste un message d'info
		frappe.msgprint({
			title: __("Action requise"),
			message: __(
				"Pour annuler cette facture, vous devez d'abord annuler manuellement les mouvements GNR dans :<br><br><strong>Menu GNR → Mouvement GNR</strong>"
			),
			indicator: "orange",
		});
	}
}
