// ==========================================
// FICHIER: gnr_compliance/public/js/sales_invoice_gnr.js
// INTERFACE pour annuler factures de vente avec mouvements GNR
// ==========================================

frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Ajouter fonctionnalités GNR si le document est soumis
		if (frm.doc.docstatus === 1) {
			add_gnr_cancel_button(frm);
			check_gnr_links(frm);
		}
	},
});

function add_gnr_cancel_button(frm) {
	// Vérifier s'il y a des mouvements GNR liés
	frappe.call({
		method: "gnr_compliance.utils.gnr_cancel_helper.get_gnr_movements_for_document",
		args: {
			doctype: "Sales Invoice",
			name: frm.doc.name,
		},
		callback: function (r) {
			if (r.message && r.message.length > 0) {
				const submitted_movements = r.message.filter((m) => m.docstatus === 1);

				if (submitted_movements.length > 0) {
					// Ajouter bouton d'annulation GNR
					frm.add_custom_button(
						__("🔄 Annuler avec GNR"),
						function () {
							show_gnr_cancel_dialog(frm, submitted_movements);
						},
						__("Actions")
					).addClass("btn-warning");

					// Ajouter message d'information
					frm.dashboard.add_comment(
						`⚠️ ${submitted_movements.length} mouvement(s) GNR actif(s) - Utilisez "Annuler avec GNR"`,
						"orange",
						true
					);
				}
			}
		},
	});
}

function check_gnr_links(frm) {
	// Vérifier et afficher les liens GNR dans le dashboard
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Mouvement GNR",
			filters: {
				reference_document: "Sales Invoice",
				reference_name: frm.doc.name,
			},
			fields: ["name", "docstatus", "type_mouvement", "quantite", "creation"],
		},
		callback: function (r) {
			if (r.message && r.message.length > 0) {
				add_gnr_info_to_dashboard(frm, r.message);
			}
		},
	});
}

function add_gnr_info_to_dashboard(frm, movements) {
	// Créer section d'information GNR dans le dashboard
	const gnr_info = movements
		.map((m) => {
			const status =
				m.docstatus === 1 ? "✅ Actif" : m.docstatus === 2 ? "❌ Annulé" : "📝 Brouillon";
			return `${m.name} - ${m.type_mouvement || "N/A"} (${m.quantite || 0}L) - ${status}`;
		})
		.join("<br>");

	frm.dashboard.add_comment(
		`<strong>📋 Mouvements GNR liés:</strong><br>${gnr_info}`,
		"blue",
		true
	);
}

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
		title: __("🔄 Annulation Facture avec GNR"),
		fields: [
			{
				fieldname: "warning_info",
				fieldtype: "HTML",
				options: `
                    <div class="alert alert-warning">
                        <h6><i class="fa fa-exclamation-triangle"></i> Documents GNR liés détectés</h6>
                        <p>Cette facture est liée à <strong>${gnr_movements.length} mouvement(s) GNR actif(s)</strong> :</p>
                        <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 4px; border-left: 4px solid #ffc107;">
                            ${movements_list}
                        </div>
                        <p><strong>⚠️ Important:</strong> L'annulation normale ne fonctionnera pas tant que ces mouvements sont actifs.</p>
                    </div>
                `,
			},
			{
				fieldname: "section_break",
				fieldtype: "Section Break",
				label: "Options d'annulation",
			},
			{
				fieldname: "action_type",
				label: "Choisissez votre action",
				fieldtype: "Select",
				options: [
					"",
					"🔄 Annuler automatiquement tout (recommandé)",
					"📋 Annuler seulement les mouvements GNR",
					"🔍 Debug - Voir tous les liens du document",
					"⚠️ Forcer l'annulation (ignorer les liens)",
				],
				reqd: 1,
				description: "Sélectionnez l'action à effectuer",
			},
			{
				fieldname: "column_break",
				fieldtype: "Column Break",
			},
			{
				fieldname: "confirm_action",
				fieldtype: "Check",
				label: "✅ Je confirme comprendre les conséquences",
				default: 0,
				description: "Confirmation requise pour procéder",
			},
		],
		size: "large",
		primary_action_label: __("Exécuter l'action"),
		primary_action: function (data) {
			if (!data.confirm_action) {
				frappe.msgprint({
					title: __("Confirmation requise"),
					message: __("Veuillez cocher la case de confirmation pour procéder"),
					indicator: "red",
				});
				return;
			}

			dialog.hide();
			execute_gnr_action(frm, data.action_type, gnr_movements);
		},
		secondary_action_label: __("Annuler"),
		secondary_action: function () {
			dialog.hide();
		},
	});

	dialog.show();
}

function execute_gnr_action(frm, action_type, movements) {
	if (action_type.includes("Annuler automatiquement tout")) {
		// Annulation complète automatique
		execute_full_cancel(frm);
	} else if (action_type.includes("Annuler seulement les mouvements")) {
		// Annulation des mouvements seulement
		execute_movements_cancel(frm);
	} else if (action_type.includes("Debug")) {
		// Mode debug
		execute_debug_mode(frm);
	} else if (action_type.includes("Forcer")) {
		// Annulation forcée
		execute_force_cancel(frm);
	}
}

function execute_full_cancel(frm) {
	frappe.show_progress(__("Annulation complète"), 0, __("Initialisation..."));

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

				// Actualiser après 2 secondes
				setTimeout(() => {
					frm.reload_doc();
					frappe.msgprint({
						title: __("Annulation réussie"),
						message: __(
							"La facture et tous ses mouvements GNR ont été annulés avec succès."
						),
						indicator: "green",
					});
				}, 2000);
			} else {
				frappe.msgprint({
					title: __("Erreur d'annulation"),
					message: r.message
						? r.message.message
						: __("Erreur inconnue lors de l'annulation"),
					indicator: "red",
				});
			}
		},
		error: function (err) {
			frappe.hide_progress();
			frappe.msgprint({
				title: __("Erreur système"),
				message: __("Erreur de communication avec le serveur. Vérifiez les logs."),
				indicator: "red",
			});
			console.error("Erreur GNR:", err);
		},
	});
}

function execute_movements_cancel(frm) {
	frappe.show_progress(__("Annulation GNR"), 0, __("Annulation des mouvements en cours..."));

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
					title: __("Mouvements GNR annulés"),
					message: __(
						'Les mouvements GNR ont été annulés avec succès.<br><br><strong>Vous pouvez maintenant annuler la facture normalement</strong> via le bouton "Annuler" standard.'
					),
					indicator: "blue",
				});

				// Actualiser pour mettre à jour l'affichage
				setTimeout(() => frm.reload_doc(), 1500);
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

function execute_debug_mode(frm) {
	frappe.call({
		method: "gnr_compliance.utils.gnr_cancel_helper.debug_document_links",
		args: {
			doctype: "Sales Invoice",
			name: frm.doc.name,
		},
		callback: function (r) {
			if (r.message) {
				const debug_info = `
                    <h6>🔍 Informations de debug pour ${frm.doc.name}</h6>
                    <p><strong>Statut document:</strong> ${r.message.document_status}</p>
                    <p><strong>Mouvements GNR:</strong> ${
						r.message.gnr_movements.length
					} trouvé(s)</p>
                    <ul>
                        ${r.message.gnr_movements
							.map((m) => `<li>${m.name} (statut: ${m.docstatus})</li>`)
							.join("")}
                    </ul>
                    <p><strong>Types de liens possibles:</strong></p>
                    <ul>
                        ${r.message.potential_links
							.map((l) => `<li>${l.link_doctype} via ${l.link_fieldname}</li>`)
							.join("")}
                    </ul>
                `;

				frappe.msgprint({
					title: __("Debug Document"),
					message: debug_info,
					indicator: "blue",
				});
			}
		},
	});
}

function execute_force_cancel(frm) {
	frappe.confirm(
		__(
			"⚠️ ATTENTION: L'annulation forcée ignore tous les liens et peut causer des incohérences de données.<br><br>Êtes-vous absolument sûr de vouloir procéder ?"
		),
		function () {
			frappe.call({
				method: "gnr_compliance.utils.gnr_cancel_helper.force_cancel_document",
				args: {
					doctype: "Sales Invoice",
					name: frm.doc.name,
				},
				callback: function (r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: __("⚠️ " + r.message.message),
							indicator: "orange",
						});
						setTimeout(() => frm.reload_doc(), 1500);
					} else {
						frappe.msgprint({
							title: __("Échec annulation forcée"),
							message: r.message
								? r.message.message
								: __("L'annulation forcée a échoué"),
							indicator: "red",
						});
					}
				},
			});
		}
	);
}
