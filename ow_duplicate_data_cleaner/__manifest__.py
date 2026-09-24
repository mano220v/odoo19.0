{
    "name": "Duplicate Data Cleaner Pro | Find & Merge",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Find, review and safely merge duplicate contacts and records with exact and fuzzy matching",
    "description": """
Duplicate Data Cleaner Pro
==========================
Find and resolve duplicate data across Odoo with configurable matching rules.

Features
--------
* Scan contacts or any stored Odoo model
* Exact, normalized and fuzzy matching
* Email, phone, text, alphanumeric, case and whitespace normalization
* Weighted confidence scores and required match criteria
* Side-by-side duplicate groups with suggested master records
* Native Odoo partner merge for contacts
* Generic reference reassignment and safe archive workflow
* Scheduled scans, ignored groups and complete merge audit logs
* Multi-company access rules and premium responsive interface
    """,
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    "price": 24.95,
    "currency": "USD",
    "depends": ["base", "mail", "web", "contacts"],
    "data": [
        "security/duplicate_cleaner_security.xml",
        "security/ir.model.access.csv",
        "data/default_rules.xml",
        "data/ir_cron.xml",
        "wizard/duplicate_merge_wizard_views.xml",
        "views/duplicate_rule_views.xml",
        "views/duplicate_scan_views.xml",
        "views/duplicate_group_views.xml",
        "views/duplicate_merge_log_views.xml",
        "views/duplicate_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ow_duplicate_data_cleaner/static/src/scss/duplicate_cleaner.scss",
        ],
    },
    "images": ["static/description/banner.png", "static/description/icon.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
}
