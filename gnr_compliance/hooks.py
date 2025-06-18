# -*- coding: utf-8 -*-
from __future__ import unicode_literals

app_name = "gnr_compliance"
app_title = "Conformité GNR"
app_publisher = "Mohamed Kachtit"
app_description = "Application de conformité réglementaire GNR"
app_icon = "octicon octicon-law"
app_color = "#2e8b57"
app_version = "0.0.1"  # Version définie directement

# Configuration après installation
after_install = "gnr_compliance.setup.install.after_install"

# === Intégration avec les modules ERPNext ===
doc_events = {
    "Sales Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_vente_gnr",
        "on_cancel": "gnr_compliance.integrations.sales.annuler_vente_gnr"
    },
    "Purchase Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_achat_gnr",
        "on_cancel": "gnr_compliance.integrations.sales.annuler_achat_gnr"
    },
    "Stock Entry": {
        "on_submit": "gnr_compliance.integrations.stock.capture_mouvement_stock",
        "on_cancel": "gnr_compliance.integrations.stock.annuler_mouvement_stock"
    },
    # Détection automatique des catégories
    "Item": {
        "validate": "gnr_compliance.utils.category_detector.detect_gnr_category",
        "after_insert": "gnr_compliance.utils.category_detector.log_category_assignment"
    }
}

# === Scripts personnalisés ===
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice_gnr.js",
    "Purchase Invoice": "public/js/purchase_invoice_gnr.js", 
    "Stock Entry": "public/js/stock_entry_gnr.js"
}

# === Champs personnalisés pour détection automatique ===
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

# === Fixtures pour l'installation ===
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "Item-gnr_tracked_category",
                "Item-is_gnr_tracked",
                "Stock Entry-gnr_categories_processed"
            ]]
        ]
    }
]