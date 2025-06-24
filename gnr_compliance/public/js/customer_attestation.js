// Fichier: gnr_compliance/public/js/customer_attestation.js

frappe.ui.form.on("Customer", {
	refresh: function (frm) {
		afficher_attestation(frm);
	},

	custom_date_de_depot: function (frm) {
		afficher_attestation(frm);
	},

	custom_n_dossier: function (frm) {
		afficher_attestation(frm);
	},
});

function afficher_attestation(frm) {
	// Supprimer l'ancien indicateur
	$("#attestation-banner").remove();

	// Vérifier si les deux champs sont remplis
	if (frm.doc.custom_date_de_depot && frm.doc.custom_n_dossier) {
		// CSS pour le clignotement
		const css = `
			<style>
			.attestation-banner {
				background: #28a745;
				color: white;
				padding: 12px 20px;
				text-align: center;
				font-weight: bold;
				font-size: 16px;
				margin: 10px 0;
				border-radius: 5px;
				animation: blink 1.5s infinite;
			}
			@keyframes blink {
				0%, 50% { opacity: 1; }
				25%, 75% { opacity: 0.5; }
			}
			</style>
		`;

		// HTML de l'indicateur
		const html = `
			${css}
			<div id="attestation-banner" class="attestation-banner">
				📋 AVEC ATTESTATION
			</div>
		`;

		// Ajouter en haut du formulaire
		$(html).insertAfter(".page-head .container");
	}
}
