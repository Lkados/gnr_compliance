# ==========================================
# FICHIER: hooks.py - CORRECTION POUR ANNULATION
# ==========================================

app_name = "gnr_compliance"
app_title = "Conformité GNR"
app_publisher = "Mohamed Kachtit"
app_description = "Application de conformité réglementaire GNR avec détection automatique"
app_icon = "octicon octicon-law"
app_color = "#2e8b57"
app_version = "1.0.1"

# Configuration après installation
after_install = "gnr_compliance.setup.install.after_install"

# === Intégration avec les modules ERPNext - CORRECTION ANNULATION ===
doc_events = {
    "Sales Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_vente_gnr",
        "before_cancel": "gnr_compliance.integrations.sales.cancel_vente_gnr",  # AVANT annulation
        "on_cancel": "gnr_compliance.integrations.sales.cleanup_after_cancel"   # APRÈS annulation
    },
    "Purchase Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_achat_gnr",
        "before_cancel": "gnr_compliance.integrations.sales.cancel_achat_gnr",  # AVANT annulation
        "on_cancel": "gnr_compliance.integrations.sales.cleanup_after_cancel_purchase"  # APRÈS annulation
    },
    "Stock Entry": {
        "on_submit": "gnr_compliance.integrations.stock.capture_mouvement_stock",
        "before_cancel": "gnr_compliance.integrations.stock.cancel_mouvement_stock"
    },
    "Item": {
        "validate": "gnr_compliance.utils.category_detector.detect_gnr_category",
        "on_update": "gnr_compliance.utils.category_detector.update_gnr_tracking"
    }
}

# Scripts personnalisés
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice_gnr.js",
    "Purchase Invoice": "public/js/purchase_invoice_gnr.js", 
    "Stock Entry": "public/js/stock_entry_gnr.js",
    "Mouvement GNR": "public/js/gnr_management.js"
}

# === Champs personnalisés ===
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
    ]
}

# Scheduled Tasks
scheduler_events = {
    "hourly": [
        "gnr_compliance.utils.gnr_utilities.auto_submit_pending_movements"
    ],
    "daily": [
        "gnr_compliance.tasks.daily_gnr_sync",
        "gnr_compliance.tasks.check_gnr_compliance"
    ]
}

# === CONFIGURATION POUR PERMETTRE ANNULATION ===
override_doctype_dashboards = {
    "Sales Invoice": "gnr_compliance.dashboard.sales_invoice_dashboard.get_dashboard_data",
    "Purchase Invoice": "gnr_compliance.dashboard.purchase_invoice_dashboard.get_dashboard_data"
}