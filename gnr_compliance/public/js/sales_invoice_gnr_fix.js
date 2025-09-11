// Fix pour le problème de récursion infinie lors de la validation des factures
// Ce fichier doit être chargé APRÈS sales_invoice_gnr.js

(function() {
    // Variable pour éviter les boucles infinies
    let isSubmitting = false;
    
    // Override du comportement de submit si nécessaire
    frappe.ui.form.on("Sales Invoice", {
        before_submit: function(frm) {
            // Empêcher les appels récursifs
            if (isSubmitting) {
                console.log("[GNR Fix] Blocage de la récursion infinie détecté");
                return false;
            }
            isSubmitting = true;
            
            // Reset après 2 secondes pour permettre une nouvelle tentative
            setTimeout(() => {
                isSubmitting = false;
            }, 2000);
        },
        
        after_submit: function(frm) {
            // Reset du flag après soumission réussie
            isSubmitting = false;
        }
    });
    
    // Protection contre les triggers récursifs
    const originalTrigger = frappe.ui.form.Form.prototype.trigger;
    frappe.ui.form.Form.prototype.trigger = function(event, ...args) {
        // Détection de boucle infinie sur le submit
        if (event === 'submit' || event === 'before_submit') {
            if (this._submitCallCount === undefined) {
                this._submitCallCount = 0;
            }
            
            this._submitCallCount++;
            
            // Si plus de 5 appels en moins de 500ms, on bloque
            if (this._submitCallCount > 5) {
                console.error("[GNR Fix] Boucle infinie détectée sur l'événement:", event);
                this._submitCallCount = 0;
                return;
            }
            
            // Reset du compteur après 500ms
            setTimeout(() => {
                this._submitCallCount = 0;
            }, 500);
        }
        
        // Appel de la méthode originale
        return originalTrigger.apply(this, [event, ...args]);
    };
    
    console.log("[GNR Fix] Protection contre les boucles infinies activée");
})();