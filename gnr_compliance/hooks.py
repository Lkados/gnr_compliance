# ==========================================
# FICHIER: hooks.py - Configuration Principale MISE À JOUR
# ==========================================

from __future__ import annotations
from typing import Dict, List, Any

app_name = "gnr_compliance"
app_title = "Conformité GNR"
app_publisher = "Mohamed Kachtit"
app_description = "Application de conformité réglementaire GNR avec détection automatique"
app_icon = "octicon octicon-law"
app_color = "#2e8b57"
app_version = "1.0.0"

# Configuration après installation
after_install = "gnr_compliance.setup.install.after_install"

# === Intégration avec les modules ERPNext ===
doc_events = {
    "Sales Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_vente_gnr",
        "on_cancel": "gnr_compliance.integrations.sales.cancel_vente_gnr"
    },
    "Purchase Invoice": {
        "on_submit": "gnr_compliance.integrations.sales.capture_achat_gnr",
        "on_cancel": "gnr_compliance.integrations.sales.cancel_achat_gnr"
    },
    "Stock Entry": {
        "on_submit": "gnr_compliance.integrations.stock.capture_mouvement_stock",
        "on_cancel": "gnr_compliance.integrations.stock.cancel_mouvement_stock"
    },
    "Item": {
        "validate": "gnr_compliance.utils.category_detector.detect_gnr_category",
        "on_update": "gnr_compliance.utils.category_detector.update_gnr_tracking"
    }
}

# === Scripts personnalisés ===
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice_gnr.js",
    "Purchase Invoice": "public/js/purchase_invoice_gnr.js", 
    "Stock Entry": "public/js/stock_entry_gnr.js",
    "Mouvement GNR": "public/js/gnr_management.js"
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

# === Scheduled Tasks MISE À JOUR ===
scheduler_events = {
    "hourly": [
        "gnr_compliance.utils.gnr_utilities.auto_submit_pending_movements"
    ],
    "daily": [
        "gnr_compliance.tasks.daily_gnr_sync",
        "gnr_compliance.tasks.check_gnr_compliance",
        "gnr_compliance.utils.cache_manager.refresh_category_cache"
    ],
    "weekly": [
        "gnr_compliance.tasks.weekly_gnr_report",
        "gnr_compliance.utils.category_detector.process_pending_categorization"
    ],
    "monthly": [
        "gnr_compliance.tasks.monthly_gnr_summary",
        "gnr_compliance.tasks.generate_quarterly_reports"
    ]
}

# === Configuration des permissions ===
permission_query_conditions = {
    "Mouvement GNR": "gnr_compliance.permissions.get_permission_query_conditions_for_mouvement_gnr",
}

has_permission = {
    "Mouvement GNR": "gnr_compliance.permissions.has_permission_mouvement_gnr",
}

# === Configuration des notifications ===
notification_config = "gnr_compliance.notifications.get_notification_config"

# === Configuration boot ===
boot_session = "gnr_compliance.boot.boot_session"

# === Jinja Environment ===
jinja = {
    "methods": [
        "gnr_compliance.utils.gnr_utilities.get_gnr_movements_summary",
        "gnr_compliance.utils.category_detector.get_tracked_categories_summary"
    ]
}

# === Configuration des rapports ===
standard_queries = {
    "Mouvement GNR": "gnr_compliance.query.mouvement_gnr_query"
}

# === Configuration des workspace ===
workspaces = [
    {
        "name": "GNR Compliance",
        "icon": "fa fa-cog",
        "color": "#2e8b57"
    }
]

# === Configuration override des méthodes ===
override_doctype_dashboards = {
    "Mouvement GNR": "gnr_compliance.dashboard.mouvement_gnr.get_data"
}

# === Configuration des vues personnalisées ===
standard_portal_menu_items = [
    {"title": "Mouvements GNR", "route": "/mouvement-gnr", "reference_doctype": "Mouvement GNR"},
]

# === Configuration de la recherche ===
global_search_doctypes = {
    "Mouvement GNR": [
        {"doctype": "Mouvement GNR", "index": 1},
        {"doctype": "GNR Movement Log", "index": 2}
    ]
}

# === Configuration des domaines ===
domains = {
    "GNR Compliance": "gnr_compliance.setup.setup_domain"
}

# === Configuration des outils d'export ===
export_python_type_map = {
    "Mouvement GNR": "gnr_compliance.utils.export.mouvement_gnr_export"
}

# === Configuration des emails ===
email_brand_image = "gnr_compliance/public/images/gnr-logo.png"

# === Configuration des tests ===
test_dependencies = ["Item", "Customer", "Supplier"]

# === Configuration de migration ===
before_migrate = [
    "gnr_compliance.patches.before_migrate.backup_gnr_data"
]

after_migrate = [
    "gnr_compliance.patches.after_migrate.update_gnr_schema",
    "gnr_compliance.patches.after_migrate.migrate_legacy_data"
]

# === Configuration de sauvegarde ===
backup_config = {
    "include_doctypes": ["Mouvement GNR", "GNR Movement Log", "GNR Category Settings"],
    "exclude_fields": ["password", "api_key"]
}

# === Configuration de logging ===
log_settings = {
    "level": "INFO",
    "formatters": {
        "verbose": {
            "format": "{asctime} {name} {levelname} {message}",
            "style": "{"
        }
    },
    "handlers": {
        "gnr_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/gnr_compliance.log",
            "maxBytes": 50000000,  # 50MB
            "backupCount": 5,
            "formatter": "verbose"
        }
    },
    "loggers": {
        "gnr_compliance": {
            "handlers": ["gnr_file"],
            "level": "INFO",
            "propagate": False
        }
    }
}