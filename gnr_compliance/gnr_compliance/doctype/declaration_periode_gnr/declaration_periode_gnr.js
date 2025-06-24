// gnr_compliance/gnr_compliance/doctype/declaration_periode_gnr/declaration_periode_gnr.js

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

			// Bouton pour vérifier les attestations clients
			frm.add_custom_button(
				"📋 Attestations Clients",
				function () {
					verifier_attestations_clients(frm);
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

	// Mettre à jour les options du champ période
	frm.set_df_property("periode", "options", options.join("\n"));
	frm.set_df_property("periode", "description", description);

	// Reset la période si elle n'est plus valide
	if (!options.includes(frm.doc.periode)) {
		frm.set_value("periode", options[0]); // Sélectionner la première option par défaut
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

	frappe.show_progress("Génération...", 50, "Calcul des données GNR");

	// Appeler directement la méthode de calcul côté serveur
	frm.call("calculer_donnees_forcees")
		.then((r) => {
			frappe.hide_progress();

			if (r.message && r.message.success) {
				// Recharger le document pour voir les nouvelles données
				frm.reload_doc();

				frappe.show_alert({
					message: r.message.message || "Déclaration générée avec succès",
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

function verifier_attestations_clients(frm) {
	frappe.show_progress("Vérification...", 50, "Analyse des attestations clients");

	frappe.call({
		method: "gnr_compliance.utils.verification_attestations.verifier_attestations_clients",
		callback: function (r) {
			frappe.hide_progress();

			if (r.message && r.message.success) {
				let data = r.message;

				let message = `
					<h5>📋 État des Attestations Clients</h5>
					
					<div class="row">
						<div class="col-sm-4">
							<h6>📊 Résumé</h6>
							<ul>
								<li><strong>Total clients :</strong> ${data.total_clients}</li>
								<li><strong>🟢 Avec attestation :</strong> ${data.avec_attestation}</li>
								<li><strong>🔴 Sans attestation :</strong> ${data.sans_attestation}</li>
								<li><strong>⚠️ Incomplets :</strong> ${data.incomplets}</li>
							</ul>
						</div>
						<div class="col-sm-8">
							<h6>💰 Impact Tarifs GNR</h6>
							<p><strong>🟢 Clients avec attestation :</strong> Tarif 3,86€/hL</p>
							<p><em>N° Dossier + Date de Dépôt remplis</em></p>
							<p><strong>🔴 Clients sans attestation :</strong> Tarif 24,81€/hL</p>
							<p><em>N° Dossier OU Date de Dépôt manquant</em></p>
						</div>
					</div>
					
					${
						data.incomplets > 0
							? `<div class="alert alert-warning">
							<strong>⚠️ ${data.incomplets} client(s) avec dossier incomplet</strong><br>
							Vérifiez que les champs "N° Dossier" ET "Date de Dépôt" sont bien remplis.
						</div>`
							: ""
					}
					
					${
						data.avec_attestation > 0
							? `<div class="alert alert-success">
							✅ ${data.avec_attestation} client(s) bénéficient du tarif réduit GNR
						</div>`
							: ""
					}
				`;

				frappe.msgprint({
					title: "Vérification Attestations",
					message: message,
					indicator: data.incomplets > 0 ? "orange" : "green",
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

function export_format(frm, format_type) {
	let format_label = format_type === "html" ? "HTML (impression/PDF)" : "CSV (Excel)";

	frappe.show_progress("Export...", 70, `Génération du fichier ${format_label}`);

	frm.call("generer_export_reglementaire", {
		format_export: format_type,
	})
		.then((r) => {
			frappe.hide_progress();

			if (r.message && r.message.success) {
				if (r.message.arrete_url && r.message.clients_url) {
					// Export annuel - deux fichiers
					frappe.msgprint({
						title: "Export Annuel Généré",
						message: `
						<p>Deux fichiers ont été générés :</p>
						<p><a href="${r.message.arrete_url}" target="_blank">📊 Arrêté Annuel de Stock</a></p>
						<p><a href="${r.message.clients_url}" target="_blank">👥 Liste Annuelle des Clients</a></p>
					`,
						indicator: "green",
					});
				} else if (r.message.file_url) {
					// Export simple
					let type_doc = "";
					if (frm.doc.type_periode === "Trimestriel") {
						type_doc = "📊 Arrêté Trimestriel de Stock Détaillé";
					} else if (frm.doc.type_periode === "Semestriel") {
						type_doc = "👥 Liste Semestrielle des Clients Douane";
					}

					frappe.show_alert({
						message: `${type_doc} généré avec succès (${format_label})`,
						indicator: "green",
					});

					// Différent comportement selon le format
					if (format_type === "html") {
						// Pour HTML, ouvrir dans un nouvel onglet
						window.open(r.message.file_url, "_blank");

						frappe.msgprint({
							title: "Export HTML Généré",
							message: `
							<p><strong>${r.message.message}</strong></p>
							<p>Le fichier HTML s'est ouvert dans un nouvel onglet.</p>
							<p><em>💡 Astuce: Utilisez Ctrl+P pour imprimer ou sauvegarder en PDF</em></p>
							<p><a href="${r.message.file_url}" target="_blank" class="btn btn-info">
								🌐 Rouvrir le fichier
							</a></p>
						`,
							indicator: "blue",
						});
					} else {
						// Pour CSV, afficher le lien de téléchargement
						frappe.msgprint({
							title: "Export CSV Généré",
							message: `
							<p><strong>${r.message.message}</strong></p>
							<p><a href="${r.message.file_url}" target="_blank" class="btn btn-primary">
								📥 Télécharger ${r.message.file_name}
							</a></p>
							<p><small><em>Format: CSV (compatible Excel) - Cliquez pour télécharger</em></small></p>
						`,
							indicator: "green",
						});
					}
				}
			} else {
				// Gestion des erreurs
				frappe.msgprint({
					title: "Export Échoué",
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
				message:
					"Erreur lors de la génération de l'export réglementaire. Vérifiez qu'il y a des données pour cette période.",
				indicator: "red",
			});
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

	frappe.show_progress("Export...", 70, `Génération ${doc_type}`);

	frm.call("generer_export_reglementaire")
		.then((r) => {
			frappe.hide_progress();

			if (r.message && r.message.success) {
				if (r.message.arrete_url && r.message.clients_url) {
					// Export annuel - deux fichiers
					frappe.msgprint({
						title: "Export Annuel Généré ✅",
						message: `
						<p><strong>Deux fichiers Excel ont été générés aux formats exacts :</strong></p>
						<div style="margin: 15px 0;">
							<p><a href="${r.message.arrete_url}" target="_blank" class="btn btn-primary" style="margin: 5px;">
								📊 Déclaration Annuelle (Comptabilité Matière)
							</a></p>
							<p><a href="${r.message.clients_url}" target="_blank" class="btn btn-success" style="margin: 5px;">
								👥 Liste Annuelle des Clients Douane
							</a></p>
						</div>
						<p><small><em>Format Excel (.xlsx) - Conforme aux exigences réglementaires</em></small></p>
					`,
						indicator: "green",
					});
				} else if (r.message.file_url) {
					// Export simple
					frappe.show_alert({
						message: `${doc_type} généré avec succès`,
						indicator: "green",
					});

					// Message détaillé selon le type
					let details_message = "";
					if (frm.doc.type_periode === "Trimestriel") {
						details_message = `
						<p><strong>✅ Déclaration Trimestrielle générée</strong></p>
						<p>📋 Format : Comptabilité Matière - Gasoil Non Routier</p>
						<p>📊 Données : Mouvements jour par jour avec stocks</p>
						<p>⚖️ Distinction : Volumes avec/sans attestation</p>
					`;
					} else if (frm.doc.type_periode === "Semestriel") {
						details_message = `
						<p><strong>✅ Liste Semestrielle des Clients générée</strong></p>
						<p>🏢 Informations distributeur et clients</p>
						<p>📊 Volumes en hectolitres (hL)</p>
						<p>💰 Tarifs d'accise : 3,86€ (avec attestation) / 24,81€ (sans attestation)</p>
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
						<p><small><em>Format Excel (.xlsx) - Exact selon vos spécifications</em></small></p>
					`,
						indicator: "green",
					});
				}
			} else {
				// Gestion des erreurs
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

			let error_details = "";
			if (error.message && error.message.includes("openpyxl")) {
				error_details = `
				<p><strong>Module manquant :</strong> openpyxl</p>
				<p>Solution : <code>bench pip install openpyxl</code></p>
			`;
			}

			frappe.msgprint({
				title: "Erreur Export",
				message: `
				<p>Erreur lors de la génération de l'export réglementaire.</p>
				${error_details}
				<p><strong>Vérifications :</strong></p>
				<ul>
					<li>Y a-t-il des mouvements GNR pour cette période ?</li>
					<li>Le module openpyxl est-il installé ?</li>
					<li>Les champs avec/sans attestation sont-ils remplis ?</li>
				</ul>
			`,
				indicator: "red",
			});
		});
}

function afficher_resume(frm) {
	// Afficher un résumé visuel des données
	if (frm.doc.total_ventes) {
		frm.dashboard.add_indicator(`Ventes: ${format_number(frm.doc.total_ventes)} L`, "blue");
	}

	if (frm.doc.total_taxe_gnr) {
		frm.dashboard.add_indicator(`Taxe: ${format_currency(frm.doc.total_taxe_gnr)}`, "green");
	}

	if (frm.doc.nb_clients) {
		frm.dashboard.add_indicator(`Clients: ${frm.doc.nb_clients}`, "orange");
	}

	// Indicateur du type de document généré
	let doc_type = "";
	if (frm.doc.type_periode === "Trimestriel") {
		doc_type = "📊 Génère: Déclaration Trimestrielle (Comptabilité Matière - GNR)";
	} else if (frm.doc.type_periode === "Semestriel") {
		doc_type = "👥 Génère: Liste Semestrielle des Clients Douane (avec tarifs d'accise)";
	} else if (frm.doc.type_periode === "Annuel") {
		doc_type = "📋 Génère: Déclaration + Liste Clients (formats exacts Excel)";
	}

	if (doc_type) {
		frm.dashboard.add_comment(doc_type, "blue", true);
	}

	// Ajout d'informations sur les tarifs GNR
	if (frm.doc.type_periode === "Semestriel" || frm.doc.type_periode === "Annuel") {
		frm.dashboard.add_comment(
			"💰 Tarifs: 3,86€/hL (N° Dossier + Date Dépôt remplis) - 24,81€/hL (champs manquants)",
			"orange",
			true
		);
	}
}

function verifier_donnees_disponibles(frm) {
	if (!frm.doc.date_debut || !frm.doc.date_fin) {
		frappe.msgprint("Veuillez d'abord sélectionner une période valide");
		return;
	}

	frappe.show_progress("Vérification...", 30, "Analyse des données disponibles");

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
						<h6>⚖️ Répartition Attestations</h6>
						<ul>
							<li><strong>🟢 Avec attestation :</strong> ${
								data.volume_avec_attestation || 0
							}L (tarif 3,86€/hL)</li>
							<li><strong>🔴 Sans attestation :</strong> ${
								data.volume_sans_attestation || 0
							}L (tarif 24,81€/hL)</li>
						</ul>
					</div>
					<div class="col-sm-6">
						<h6>👥 Clients par type</h6>
						<ul>
							<li><strong>🟢 Agricoles/Forestiers :</strong> ${data.clients_avec_attestation || 0}</li>
							<li><strong>🔴 Autres clients :</strong> ${data.clients_sans_attestation || 0}</li>
						</ul>
					</div>
				</div>
				
				${
					data.total_mouvements === 0
						? '<div class="alert alert-warning">⚠️ Aucun mouvement GNR trouvé pour cette période</div>'
						: '<div class="alert alert-success">✅ Données disponibles pour génération</div>'
				}
				
				${
					data.total_mouvements > 0 &&
					!data.volume_avec_attestation &&
					!data.volume_sans_attestation
						? '<div class="alert alert-info">💡 Vérifiez que les champs "N° Dossier" et "Date de Dépôt" sont remplis sur les fiches clients agricoles</div>'
						: ""
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
