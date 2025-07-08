frappe.ui.form.on("Customer", {
	refresh: function (frm) {
		afficher_attestation_avec_expiration(frm);
	},

	custom_date_de_depot: function (frm) {
		afficher_attestation_avec_expiration(frm);
	},

	custom_n_dossier_: function (frm) {
		afficher_attestation_avec_expiration(frm);
	},
});

function afficher_attestation_avec_expiration(frm) {
	// Supprimer l'ancien indicateur
	$("#attestation-banner").remove();

	// Vérifier si les deux champs sont remplis
	if (frm.doc.custom_date_de_depot && frm.doc.custom_n_dossier_) {
		// Calculer les dates
		const dateDepot = new Date(frm.doc.custom_date_de_depot);
		const dateExpiration = new Date(dateDepot);
		dateExpiration.setFullYear(dateExpiration.getFullYear() + 3); // +3 ans

		const dateAlerte = new Date(dateExpiration);
		dateAlerte.setMonth(dateAlerte.getMonth() - 3); // -3 mois avant expiration

		const aujourd_hui = new Date();

		let message, couleur, classe_css;

		// Déterminer le statut
		if (aujourd_hui > dateExpiration) {
			// PÉRIMÉE
			message = "⚠️ ATTESTATION PÉRIMÉE";
			couleur = "#dc3545"; // Rouge
			classe_css = "attestation-perimee";
		} else if (aujourd_hui > dateAlerte) {
			// BIENTÔT EXPIRÉE
			const joursRestants = Math.ceil(
				(dateExpiration - aujourd_hui) / (1000 * 60 * 60 * 24)
			);
			message = `⚠️ ATTESTATION BIENTOT EXPIRER (${joursRestants} jours)`;
			couleur = "#ff8c00"; // Orange
			classe_css = "attestation-alerte";
		} else {
			// VALIDE
			message = "📋 TARIF D'ACCISE RÉDUIT SUR LE GNR";
			couleur = "#28a745"; // Vert
			classe_css = "attestation-valide";
		}

		// CSS pour l'affichage
		const css = `
			<style>
			.attestation-banner {
				color: white;
				padding: 12px 20px;
				text-align: center;
				font-weight: bold;
				font-size: 16px;
				margin: 10px 0;
				border-radius: 5px;
				background-color: ${couleur};
			}
			.attestation-perimee {
				animation: flash 1s infinite;
			}
			.attestation-alerte {
				animation: pulse 2s infinite;
			}
			.attestation-valide {
				animation: fadeIn 1s;
			}
			@keyframes flash {
				0%, 50% { opacity: 1; }
				25%, 75% { opacity: 0.3; }
			}
			@keyframes pulse {
				0% { opacity: 1; }
				50% { opacity: 0.7; }
				100% { opacity: 1; }
			}
			@keyframes fadeIn {
				from { opacity: 0; }
				to { opacity: 1; }
			}
			</style>
		`;

		// HTML de l'indicateur avec info expiration
		const dateExpirationTexte = dateExpiration.toLocaleDateString("fr-FR");
		const html = `
			${css}
			<div id="attestation-banner" class="attestation-banner ${classe_css}">
				${message}
				<br><small>Expire le : ${dateExpirationTexte}</small>
			</div>
		`;

		// Ajouter en haut du formulaire
		$(html).insertAfter(".page-head .container");

		// Ajouter aussi dans le dashboard pour info
		if (aujourd_hui > dateExpiration) {
			frm.dashboard.add_indicator("Attestation PÉRIMÉE", "red");
		} else if (aujourd_hui > dateAlerte) {
			frm.dashboard.add_indicator("Attestation expire bientôt", "orange");
		} else {
			frm.dashboard.add_indicator("Attestation valide", "green");
		}
	}
}

// Fonction utilitaire pour vérifier l'expiration (utilisable ailleurs)
function verifier_expiration_attestation(date_depot) {
	if (!date_depot) return "SANS_ATTESTATION";

	const dateDepot = new Date(date_depot);
	const dateExpiration = new Date(dateDepot);
	dateExpiration.setFullYear(dateExpiration.getFullYear() + 3);

	const dateAlerte = new Date(dateExpiration);
	dateAlerte.setMonth(dateAlerte.getMonth() - 3);

	const aujourd_hui = new Date();

	if (aujourd_hui > dateExpiration) {
		return "PERIMEE";
	} else if (aujourd_hui > dateAlerte) {
		return "BIENTOT_EXPIRER";
	} else {
		return "VALIDE";
	}
}
