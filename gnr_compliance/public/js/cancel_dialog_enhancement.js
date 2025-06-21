// ==========================================
// FICHIER: public/js/cancel_dialog_enhancement.js
// AMÉLIORATION du popup d'annulation pour inclure option GNR
// ==========================================

$(document).ready(function () {
	// Intercepter le popup d'annulation d'ERPNext
	frappe.ui.form.Form.prototype.original_cancel_doc = frappe.ui.form.Form.prototype.cancel_doc;

	frappe.ui.form.Form.prototype.cancel_doc = function () {
		const me = this;

		// Vérifier si c'est une facture avec mouvements GNR
		if (
			(me.doc.doctype === "Sales Invoice" || me.doc.doctype === "Purchase Invoice") &&
			me.doc.docstatus === 1
		) {
			check_gnr_movements_and_enhance_cancel(me);
		} else {
			// Utiliser la méthode originale pour les autres doctypes
			me.original_cancel_doc();
		}
	};
});

function check_gnr_movements_and_enhance_cancel(frm) {
	// Vérifier s'il y a des mouvements GNR liés
	frappe.call({
		method: "gnr_compliance.utils.gnr_cancel_helper.get_gnr_movements_for_document",
		args: {
			doctype: frm.doc.doctype,
			name: frm.doc.name,
		},
		callback: function (r) {
			if (r.message && r.message.length > 0) {
				const submitted_movements = r.message.filter((m) => m.docstatus === 1);

				if (submitted_movements.length > 0) {
					show_enhanced_cancel_dialog(frm, submitted_movements);
				} else {
					// Pas de mouvements soumis, annulation normale
					frm.original_cancel_doc();
				}
			} else {
				// Pas de mouvements GNR, annulation normale
				frm.original_cancel_doc();
			}
		},
	});
}

function show_enhanced_cancel_dialog(frm, gnr_movements) {
	const dialog = new frappe.ui.Dialog({
		title: __("Annuler la facture"),
		fields: [
			{
				fieldname: "info",
				fieldtype: "HTML",
				options: `
                    <div class="alert alert-warning">
                        <h5><i class="fa fa-exclamation-triangle"></i> Documents liés détectés</h5>
                        <p>Cette facture est liée à <strong>${
							gnr_movements.length
						} mouvement(s) GNR</strong> :</p>
                        <ul>
                            ${gnr_movements
								.map(
									(m) =>
										`<li><strong>${m.name}</strong> - ${m.type_mouvement} (${
											m.quantite || 0
										} L)</li>`
								)
								.join("")}
                        </ul>
                    </div>
                `,
			},
			{
				fieldname: "section_break",
				fieldtype: "Section Break",
			},
			{
				fieldname: "action_choice",
				label: "Que souhaitez-vous faire ?",
				fieldtype: "Select",
				options: [
					"Annuler automatiquement les mouvements GNR puis la facture",
					"Annuler uniquement les mouvements GNR (garder la facture)",
					"Annuler juste la facture (vous devrez annuler les mouvements manuellement)",
				],
				default: "Annuler automatiquement les mouvements GNR puis la facture",
				reqd: 1,
			},
			{
				fieldname: "confirmation",
				fieldtype: "Check",
				label: "Je confirme vouloir procéder à cette annulation",
				default: 0,
			},
		],
		primary_action_label: __("Procéder"),
		primary_action: function (data) {
			if (!data.confirmation) {
				frappe.msgprint(__("Veuillez confirmer l'annulation"));
				return;
			}

			dialog.hide();

			switch (data.action_choice) {
				case "Annuler automatiquement les mouvements GNR puis la facture":
					cancel_gnr_and_invoice(frm);
					break;

				case "Annuler uniquement les mouvements GNR (garder la facture)":
					cancel_only_gnr_movements(frm);
					break;

				case "Annuler juste la facture (vous devrez annuler les mouvements manuellement)":
					frappe.msgprint({
						title: __("Action requise"),
						message: __(
							"Vous devez d'abord annuler manuellement les mouvements GNR dans le menu GNR > Mouvement GNR"
						),
						indicator: "orange",
					});
					break;
			}
		},
		secondary_action_label: __("Annuler"),
		secondary_action: function () {
			dialog.hide();
		},
	});

	dialog.show();
}

function cancel_gnr_and_invoice(frm) {
	frappe.show_progress(__("Annulation en cours..."), 50, __("Annulation des mouvements GNR"));

	frappe.call({
		method: "gnr_compliance.utils.gnr_cancel_helper.cancel_invoice_with_gnr",
		args: {
			doctype: frm.doc.doctype,
			name: frm.doc.name,
		},
		callback: function (r) {
			frappe.hide_progress();

			if (r.message && r.message.success) {
				frappe.show_alert({
					message: r.message.message,
					indicator: "green",
				});
				frm.reload_doc();
			} else {
				frappe.msgprint({
					title: __("Erreur"),
					message: r.message ? r.message.message : __("Erreur lors de l'annulation"),
					indicator: "red",
				});
			}
		},
	});
}

function cancel_only_gnr_movements(frm) {
	frappe.show_progress(__("Annulation des mouvements GNR..."), 70, __("Traitement en cours"));

	frappe.call({
		method: "gnr_compliance.utils.gnr_cancel_helper.cancel_related_gnr_movements",
		args: {
			doctype: frm.doc.doctype,
			name: frm.doc.name,
		},
		callback: function (r) {
			frappe.hide_progress();

			if (r.message !== undefined) {
				frappe.show_alert({
					message: __(`${r.message} mouvement(s) GNR annulé(s) avec succès`),
					indicator: "green",
				});

				frappe.msgprint({
					title: __("Mouvements GNR annulés"),
					message: __(
						"Vous pouvez maintenant annuler la facture normalement si souhaité."
					),
					indicator: "blue",
				});
			} else {
				frappe.msgprint({
					title: __("Erreur"),
					message: __("Erreur lors de l'annulation des mouvements GNR"),
					indicator: "red",
				});
			}
		},
	});
}
