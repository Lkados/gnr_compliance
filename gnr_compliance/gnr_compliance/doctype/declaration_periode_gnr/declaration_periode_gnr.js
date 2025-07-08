frappe.ui.form.on("Declaration Periode GNR", {
	refresh: function (frm) {
		// Ajouter boutons d'action simples
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button("📊 Générer", function () {
				generer_declaration(frm);
			}).addClass("btn-primary");

			// Bouton debug pour vérifier les données disponibles
			frm.add_custom_button(
				"🔍 Vérifier Données",
				function () {
					verifier_donnees_disponibles(frm);
				},
				__("Diagnostic")
			).addClass("btn-secondary");

			// Bouton pour vérifier les attestations clients AVEC EXPIRATION
			frm.add_custom_button(
				"📋 Attestations & Expiration",
				function () {
					verifier_attestations_avec_expiration(frm);
				},
				__("Diagnostic")
			).addClass("btn-info");
		}

		if (frm.doc.docstatus === 1) {
			// Texte du bouton selon le type de période
			let button_text = "📄 Export";
			if (frm.doc.type_periode === "Trimestriel") {
				button_text = "📊 Déclaration Trimestrielle";
			} else if (frm.doc.type_periode === "Semestriel") {
				button_text = "👥 Liste Clients Douane";
			} else if (frm.doc.type_periode === "Annuel") {
				button_text = "📋 Export Annuel";
			}

			frm.add_custom_button(button_text, function () {
				export_format_exact(frm);
			}).addClass("btn-success");
		}

		// Afficher résumé si soumis
		if (frm.doc.docstatus === 1) {
			afficher_resume(frm);
		}
	},

	type_periode: function (frm) {
		// Mettre à jour les options de période selon le type
		mettre_a_jour_periodes(frm);
		calculer_dates(frm);
	},

	periode: function (frm) {
		calculer_dates(frm);
	},

	annee: function (frm) {
		calculer_dates(frm);
	},
});

function verifier_attestations_avec_expiration(frm) {
	frappe.show_progress("Vérification...", 50, "Analyse des attestations et expirations");

	frappe.call({
		method: "gnr_compliance.utils.verification_attestations.verifier_attestations_clients",
		callback: function (r) {
			frappe.hide_progress();

			if (r.message && r.message.success) {
				let data = r.message;

				let message = `
					<h5>📋 État des Attestations Clients avec Expiration</h5>
					
					<div class="row">
						<div class="col-sm-6">
							<h6>📊 Résumé</h6>
							<ul>
								<li><strong>Total clients :</strong> ${data.total_clients}</li>
								<li><strong>🟢 Attestations valides :</strong> ${data.avec_attestation}</li>
								<li><strong>🟠 Bientôt expirer :</strong> ${data.bientot_expirer}</li>
								<li><strong>🔴 Expirées :</strong> ${data.expires}</li>
								<li><strong>❌ Sans attestation :</strong> ${data.sans_attestation}</li>
								<li><strong>⚠️ Incomplets :</strong> ${data.incomplets}</li>
							</ul>
						</div>
						<div class="col-sm-6">
							<h6>ℹ️ Information Tarifs</h6>
							<p><strong>🟢 Attestation valide :</strong> Tarif d'accise réduit (3,86€/hL)</p>
							<p><strong>🟠 Bientôt expirer :</strong> Encore valide mais à renouveler</p>
							<p><strong>🔴 Expirée :</strong> Tarif normal (24,81€/hL)</p>
							<p><strong>❌ Sans attestation :</strong> Tarif normal (24,81€/hL)</p>
						</div>
					</div>
				`;

				// Alertes spécifiques
				if (data.expires > 0) {
					message += `
						<div class="alert alert-danger">
							<strong>⚠️ ${data.expires} client(s) avec attestation PÉRIMÉE</strong><br>
							Ces clients sont facturés au tarif normal automatiquement.
						</div>
					`;
				}

				if (data.bientot_expirer > 0) {
					message += `
						<div class="alert alert-warning">
							<strong>⏰ ${data.bientot_expirer} client(s) avec attestation qui expire bientôt</strong><br>
							Prévenir ces clients pour renouveler leur attestation.
						</div>
					`;
				}

				if (data.avec_attestation > 0) {
					message += `
						<div class="alert alert-success">
							✅ ${data.avec_attestation} client(s) avec attestation valide (tarif réduit)
						</div>
					`;
				}

				// Afficher détails clients à renouveler si nécessaire
				if (
					data.details.clients_bientot_expirer &&
					data.details.clients_bientot_expirer.length > 0
				) {
					message += `<h6>🟠 Clients à renouveler prochainement :</h6><ul>`;
					data.details.clients_bientot_expirer.slice(0, 5).forEach(function (client) {
						message += `<li><strong>${client.nom}</strong> - Expire le ${client.date_expiration} (${client.jours_restants} jours)</li>`;
					});
					if (data.details.clients_bientot_expirer.length > 5) {
						message += `<li>... et ${
							data.details.clients_bientot_expirer.length - 5
						} autres</li>`;
					}
					message += `</ul>`;
				}

				frappe.msgprint({
					title: "Vérification Attestations & Expiration",
					message: message,
					indicator:
						data.expires > 0 ? "red" : data.bientot_expirer > 0 ? "orange" : "green",
				});
			} else {
				frappe.msgprint({
					title: "Erreur",
					message: r.message ? r.message.message : "Erreur lors de la vérification",
					indicator: "red",
				});
			}
		},
	});
}

// Fonctions existantes (gardées identiques)
function mettre_a_jour_periodes(frm) {
	let options = [];
	let description = "";

	if (frm.doc.type_periode === "Trimestriel") {
		options = ["T1", "T2", "T3", "T4"];
		description = "T1 (Jan-Mar), T2 (Avr-Juin), T3 (Juil-Sep), T4 (Oct-Déc)";
	} else if (frm.doc.type_periode === "Semestriel") {
		options = ["S1", "S2"];
		description = "S1 (Jan-Juin), S2 (Juil-Déc)";
	} else if (frm.doc.type_periode === "Annuel") {
		options = ["ANNEE"];
		description = "Année complète";
	}

	frm.set_df_property("periode", "options", options.join("\n"));
	frm.set_df_property("periode", "description", description);

	if (!options.includes(frm.doc.periode)) {
		frm.set_value("periode", options[0]);
	}

	frm.refresh_field("periode");
}

function calculer_dates(frm) {
	if (!frm.doc.type_periode || !frm.doc.periode || !frm.doc.annee) {
		return;
	}

	let dates = obtenir_dates_periode(frm.doc.type_periode, frm.doc.periode, frm.doc.annee);

	if (dates) {
		frm.set_value("date_debut", dates.debut);
		frm.set_value("date_fin", dates.fin);
	}
}

function obtenir_dates_periode(type, periode, annee) {
	if (type === "Trimestriel") {
		let trimestre = parseInt(periode.replace("T", ""));
		let mois_debut = (trimestre - 1) * 3 + 1;
		let mois_fin = trimestre * 3;

		return {
			debut: `${annee}-${mois_debut.toString().padStart(2, "0")}-01`,
			fin: `${annee}-${mois_fin.toString().padStart(2, "0")}-${new Date(
				annee,
				mois_fin,
				0
			).getDate()}`,
		};
	} else if (type === "Semestriel") {
		let semestre = parseInt(periode.replace("S", ""));
		if (semestre === 1) {
			return { debut: `${annee}-01-01`, fin: `${annee}-06-30` };
		} else {
			return { debut: `${annee}-07-01`, fin: `${annee}-12-31` };
		}
	} else if (type === "Annuel") {
		return { debut: `${annee}-01-01`, fin: `${annee}-12-31` };
	}
	return null;
}

function generer_declaration(frm) {
	if (!frm.doc.date_debut || !frm.doc.date_fin) {
		frappe.msgprint("Veuillez sélectionner une période valide");
		return;
	}

	frappe.show_progress(
		"Génération...",
		50,
		"Calcul des données GNR avec vérification expiration"
	);

	frm.call("calculer_donnees_forcees")
		.then((r) => {
			frappe.hide_progress();

			if (r.message && r.message.success) {
				frm.reload_doc();

				frappe.show_alert({
					message:
						r.message.message || "Déclaration générée avec vérification expiration",
					indicator: "green",
				});
			} else {
				frappe.msgprint({
					title: "Génération terminée",
					message: r.message
						? r.message.message
						: "Aucune donnée trouvée pour cette période",
					indicator: "orange",
				});
			}
		})
		.catch((error) => {
			frappe.hide_progress();
			frappe.msgprint({
				title: "Erreur",
				message: "Erreur lors du calcul des données",
				indicator: "red",
			});
			console.error("Erreur génération:", error);
		});
}

function export_format_exact(frm) {
	let doc_type = "";
	if (frm.doc.type_periode === "Trimestriel") {
		doc_type = "Déclaration Trimestrielle (Comptabilité Matière)";
	} else if (frm.doc.type_periode === "Semestriel") {
		doc_type = "Liste Semestrielle des Clients Douane";
	} else if (frm.doc.type_periode === "Annuel") {
		doc_type = "Export Annuel (Déclaration + Liste Clients)";
	}

	frappe.show_progress("Export...", 70, `Génération ${doc_type} avec gestion expiration`);

	frm.call("generer_export_reglementaire")
		.then((r) => {
			frappe.hide_progress();

			if (r.message && r.message.success) {
				if (r.message.arrete_url && r.message.clients_url) {
					frappe.msgprint({
						title: "Export Annuel Généré ✅",
						message: `
						<p><strong>Deux fichiers Excel générés avec gestion d'expiration :</strong></p>
						<div style="margin: 15px 0;">
							<p><a href="${r.message.arrete_url}" target="_blank" class="btn btn-primary" style="margin: 5px;">
								📊 Déclaration Annuelle (Comptabilité Matière)
							</a></p>
							<p><a href="${r.message.clients_url}" target="_blank" class="btn btn-success" style="margin: 5px;">
								👥 Liste Annuelle des Clients Douane
							</a></p>
						</div>
						<p><small><em>Format Excel (.xlsx) - Avec distinction attestations valides/expirées</em></small></p>
					`,
						indicator: "green",
					});
				} else if (r.message.file_url) {
					let details_message = "";
					if (frm.doc.type_periode === "Trimestriel") {
						details_message = `
						<p><strong>✅ Déclaration Trimestrielle générée</strong></p>
						<p>📋 Format : Comptabilité Matière - Gasoil Non Routier</p>
						<p>📊 Données : Mouvements avec distinction attestations valides/expirées</p>
						<p>⚖️ Tarifs appliqués automatiquement selon statut attestation</p>
					`;
					} else if (frm.doc.type_periode === "Semestriel") {
						details_message = `
						<p><strong>✅ Liste Semestrielle des Clients générée</strong></p>
						<p>🏢 Informations distributeur et clients</p>
						<p>📊 Volumes en hectolitres (hL)</p>
						<p>📋 Distinction automatique : valides/expirées/sans attestation</p>
					`;
					}

					frappe.msgprint({
						title: "Export Généré",
						message: `
						${details_message}
						<div style="margin: 15px 0;">
							<a href="${r.message.file_url}" target="_blank" class="btn btn-primary">
								📥 Télécharger ${r.message.file_name}
							</a>
						</div>
						<p><small><em>Format Excel (.xlsx) - Avec gestion automatique expiration attestations</em></small></p>
					`,
						indicator: "green",
					});
				}
			} else {
				frappe.msgprint({
					title: "Export Échoué ❌",
					message: r.message
						? r.message.message
						: "Erreur inconnue lors de la génération",
					indicator: "red",
				});
			}
		})
		.catch((error) => {
			frappe.hide_progress();
			console.error("Erreur export:", error);

			frappe.msgprint({
				title: "Erreur Export",
				message: `
				<p>Erreur lors de la génération de l'export réglementaire.</p>
				<p><strong>Vérifications :</strong></p>
				<ul>
					<li>Y a-t-il des mouvements GNR pour cette période ?</li>
					<li>Le module openpyxl est-il installé ?</li>
					<li>Les attestations clients sont-elles à jour ?</li>
				</ul>
			`,
				indicator: "red",
			});
		});
}

function afficher_resume(frm) {
	if (frm.doc.total_ventes) {
		frm.dashboard.add_indicator(`Ventes: ${format_number(frm.doc.total_ventes)} L`, "blue");
	}

	if (frm.doc.total_taxe_gnr) {
		frm.dashboard.add_indicator(`Taxe: ${format_currency(frm.doc.total_taxe_gnr)}`, "green");
	}

	if (frm.doc.nb_clients) {
		frm.dashboard.add_indicator(`Clients: ${frm.doc.nb_clients}`, "orange");
	}

	let doc_type = "";
	if (frm.doc.type_periode === "Trimestriel") {
		doc_type = "📊 Génère: Déclaration Trimestrielle (avec gestion expiration)";
	} else if (frm.doc.type_periode === "Semestriel") {
		doc_type = "👥 Génère: Liste Clients (avec statut attestations)";
	} else if (frm.doc.type_periode === "Annuel") {
		doc_type = "📋 Génère: Export Annuel (avec expiration automatique)";
	}

	if (doc_type) {
		frm.dashboard.add_comment(doc_type, "blue", true);
	}

	frm.dashboard.add_comment(
		"🔄 Tarifs appliqués automatiquement : Valide (3,86€/hL) / Expirée ou Sans (24,81€/hL)",
		"orange",
		true
	);
}

function verifier_donnees_disponibles(frm) {
	if (!frm.doc.date_debut || !frm.doc.date_fin) {
		frappe.msgprint("Veuillez d'abord sélectionner une période valide");
		return;
	}

	frappe.show_progress("Vérification...", 30, "Analyse des données avec expiration");

	frm.call("diagnostiquer_donnees").then((r) => {
		frappe.hide_progress();

		if (r.message) {
			let data = r.message;

			let message = `
				<h5>🔍 Diagnostic des données GNR</h5>
				<p><strong>Période :</strong> ${frm.doc.date_debut} au ${frm.doc.date_fin}</p>
				
				<div class="row">
					<div class="col-sm-6">
						<h6>📊 Mouvements GNR</h6>
						<ul>
							<li><strong>Total :</strong> ${data.total_mouvements}</li>
							<li><strong>Ventes :</strong> ${data.ventes}</li>
							<li><strong>Achats :</strong> ${data.achats}</li>
							<li><strong>Autres :</strong> ${data.autres}</li>
						</ul>
					</div>
					<div class="col-sm-6">
						<h6>💰 Totaux calculés</h6>
						<ul>
							<li><strong>Quantité totale :</strong> ${data.quantite_totale}L</li>
							<li><strong>Taxe GNR :</strong> ${data.taxe_totale}€</li>
							<li><strong>Clients uniques :</strong> ${data.clients_uniques}</li>
						</ul>
					</div>
				</div>
				
				<div class="row">
					<div class="col-sm-6">
						<h6>⚖️ Tarifs selon attestations</h6>
						<ul>
							<li><strong>🟢 Attestations valides :</strong> ${
								data.volume_avec_attestation || 0
							}L (3,86€/hL)</li>
							<li><strong>🔴 Expirées/Sans :</strong> ${data.volume_sans_attestation || 0}L (24,81€/hL)</li>
						</ul>
					</div>
					<div class="col-sm-6">
						<h6>👥 Clients par statut</h6>
						<ul>
							<li><strong>🟢 Avec attestation valide :</strong> ${data.clients_avec_attestation || 0}</li>
							<li><strong>🔴 Autres clients :</strong> ${data.clients_sans_attestation || 0}</li>
						</ul>
					</div>
				</div>
				
				${
					data.total_mouvements === 0
						? '<div class="alert alert-warning">⚠️ Aucun mouvement GNR trouvé pour cette période</div>'
						: '<div class="alert alert-success">✅ Données disponibles pour génération avec gestion d\'expiration</div>'
				}
			`;

			frappe.msgprint({
				title: "Diagnostic des Données",
				message: message,
				indicator: data.total_mouvements > 0 ? "green" : "orange",
			});
		}
	});
}
