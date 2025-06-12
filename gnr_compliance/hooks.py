# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "gnr_compliance"
app_title = "Conformité GNR"
app_publisher = "Mohamed Kachtit"
app_description = "Application de conformité réglementaire GNR"
app_icon = "octicon octicon-law"
app_color = "#2e8b57"

after_install = "gnr_compliance.setup.install.after_install"

# Intégration avec les modules ERPNext existants
doc_events = {
    "Sales Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_vente_gnr",
        "on_cancel": "gnr_compliance.integrations.sales.annuler_vente_gnr"
    },
    "Purchase Invoice": {
        "on_submit": "gnr_compliance.integrations.purchase.capture_achat_gnr",
        "on_cancel": "gnr_compliance.integrations.purchase.annuler_achat_gnr"
    },
    "Stock Entry": {
        "on_submit": "gnr_compliance.integrations.stock.capture_mouvement_stock",
        "on_cancel": "gnr_compliance.integrations.stock.annuler_mouvement_stock"
    }
}

# Tâches programmées pour les déclarations
scheduler_events = {
    "monthly": [
        "gnr_compliance.tasks.generer_declaration_mensuelle"
    ],
    "daily": [
        "gnr_compliance.tasks.verifier_echeances_declaration"
    ]
}

# Scripts personnalisés par DocType
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice_gnr.js",
    "Purchase Invoice": "public/js/purchase_invoice_gnr.js",
    "Stock Entry": "public/js/stock_entry_gnr.js"
}

# Fixtures pour l'installation
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "Sales Invoice-gnr_applicable",
                "Sales Invoice-code_gnr",
                "Sales Invoice-taux_gnr",
                "Purchase Invoice-fournisseur_gnr",
                "Stock Entry-type_carburant"
            ]]
        ]
    }
]