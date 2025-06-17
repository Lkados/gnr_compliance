# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "gnr_compliance"
app_title = "Conformité GNR"
app_publisher = "Mohamed Kachtit"
app_description = "Application de conformité réglementaire GNR"
app_icon = "octicon octicon-law"
app_color = "#2e8b57"

# Configuration après installation
after_install = "gnr_compliance.setup.install.after_install"

# === [EXISTANT] Intégration avec les modules ERPNext ===
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
    },
    # === [NOUVEAU] Détection automatique des catégories ===
    "Item": {
        "validate": "gnr_compliance.utils.category_detector.detect_gnr_category",
        "after_insert": "gnr_compliance.utils.category_detector.log_category_assignment"
    }
}

# === [EXISTANT] Tâches programmées ===
scheduler_events = {
    "monthly": [
        "gnr_compliance.tasks.generer_declaration_mensuelle"
    ],
    "daily": [
        "gnr_compliance.tasks.verifier_echeances_declaration",
        "gnr_compliance.utils.cache_manager.refresh_category_cache"  # [NOUVEAU]
    ],
    "hourly": [
        "gnr_compliance.utils.category_detector.process_pending_categorization"  # [NOUVEAU]
    ]
}

# === [EXISTANT] Scripts personnalisés ===
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice_gnr.js",
    "Purchase Invoice": "public/js/purchase_invoice_gnr.js",
    "Stock Entry": "public/js/stock_entry_gnr.js"
}

# === [NOUVEAU] Champs personnalisés pour détection automatique ===
custom_fields = {
    "Item": [
        {
            "fieldname": "gnr_tracked_category",
            "label": "Catégorie GNR",
            "fieldtype": "Data",
            "read_only": 1,
            "insert_after": "item_group",
            "translatable": 0
        },
        {
            "fieldname": "is_gnr_tracked",
            "label": "Article GNR",
            "fieldtype": "Check",
            "default": "0",
            "insert_after": "gnr_tracked_category"
        }
    ],
    "Stock Entry": [
        {
            "fieldname": "gnr_categories_processed",
            "label": "Catégories GNR Traitées",
            "fieldtype": "Check",
            "default": "0",
            "hidden": 1,
            "insert_after": "posting_time"
        }
    ]
}

# === [EXISTANT] Fixtures pour l'installation ===
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "Sales Invoice-gnr_applicable",
                "Sales Invoice-code_gnr", 
                "Sales Invoice-taux_gnr",
                "Purchase Invoice-fournisseur_gnr",
                "Stock Entry-type_carburant",
                "Item-gnr_tracked_category",     # [NOUVEAU]
                "Item-is_gnr_tracked"           # [NOUVEAU]
            ]]
        ]
    }
]