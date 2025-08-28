# ==========================================
# FICHIER: gnr_compliance/gnr_compliance/hooks.py - VERSION CORRIGÉE
# ==========================================

from __future__ import annotations
from typing import Dict, List, Any

app_name = "gnr_compliance"
app_title = "Conformité GNR"
app_publisher = "Mohamed Kachtit"
app_description = "Application de conformité réglementaire GNR avec détection automatique et gestion d'annulation"
app_icon = "octicon octicon-law"
app_color = "#2e8b57"
app_version = "1.1.0"

# === Intégration avec les modules ERPNext ===
doc_events = {
    "Sales Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_vente_gnr",
        "on_cancel": "gnr_compliance.integrations.sales.cleanup_after_cancel"
    },
    "Purchase Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_achat_gnr",
        "on_cancel": "gnr_compliance.integrations.sales.cleanup_after_cancel_purchase"
    },
    "Stock Entry": {
        "on_submit": "gnr_compliance.integrations.stock.capture_mouvement_stock",
        "before_cancel": "gnr_compliance.integrations.stock.cancel_mouvement_stock"
    }
}

# === Scripts personnalisés par DocType ===
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice_gnr.js",
    "Purchase Invoice": "public/js/purchase_invoice_gnr.js", 
    "Stock Entry": "public/js/stock_entry_gnr.js",
    "Customer": "public/js/customer_attestation.js"
}

# === Champs personnalisés unifiés ===
custom_fields = {
    "Item": [
        {
            "fieldname": "gnr_section",
            "label": "Configuration GNR",
            "fieldtype": "Section Break",
            "insert_after": "item_group",
            "collapsible": 1
        },
        {
            "fieldname": "is_gnr_tracked",
            "label": "Article GNR Tracké",
            "fieldtype": "Check",
            "default": "0",
            "insert_after": "gnr_section"
        },
        {
            "fieldname": "gnr_tracked_category",
            "label": "Catégorie GNR",
            "fieldtype": "Data",
            "read_only": 1,
            "default": "GNR",
            "depends_on": "is_gnr_tracked",
            "insert_after": "is_gnr_tracked"
        },
        {
            "fieldname": "gnr_tax_rate",
            "label": "Taux Taxe GNR (€/hL)",
            "fieldtype": "Currency",
            "depends_on": "is_gnr_tracked",
            "insert_after": "gnr_tracked_category"
        },
        {
            "fieldname": "gnr_column_break",
            "fieldtype": "Column Break",
            "insert_after": "gnr_tax_rate"
        },
        {
            "fieldname": "gnr_auto_assigned",
            "label": "Assignation Automatique",
            "fieldtype": "Check",
            "read_only": 1,
            "depends_on": "is_gnr_tracked",
            "insert_after": "gnr_column_break"
        },
        {
            "fieldname": "gnr_last_updated",
            "label": "Dernière MAJ Catégorie",
            "fieldtype": "Datetime",
            "read_only": 1,
            "depends_on": "is_gnr_tracked",
            "insert_after": "gnr_auto_assigned"
        }
    ],
    "Stock Entry": [
        {
            "fieldname": "gnr_processing_section",
            "label": "Traitement GNR",
            "fieldtype": "Section Break",
            "insert_after": "posting_time",
            "collapsible": 1,
            "collapsible_depends_on": "gnr_items_detected"
        },
        {
            "fieldname": "gnr_items_detected",
            "label": "Articles GNR Détectés",
            "fieldtype": "Int",
            "read_only": 1,
            "default": "0",
            "insert_after": "gnr_processing_section"
        },
        {
            "fieldname": "gnr_categories_processed",
            "label": "Catégories GNR Traitées",
            "fieldtype": "Check",
            "default": "0",
            "read_only": 1,
            "insert_after": "gnr_items_detected"
        }
    ]
}

# === Fixtures pour l'installation ===
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "Item-gnr_section",
                "Item-is_gnr_tracked",
                "Item-gnr_tracked_category",
                "Item-gnr_tax_rate",
                "Item-gnr_column_break",
                "Item-gnr_auto_assigned",
                "Item-gnr_last_updated",
                "Stock Entry-gnr_processing_section",
                "Stock Entry-gnr_items_detected",
                "Stock Entry-gnr_categories_processed"
            ]]
        ]
    }
]