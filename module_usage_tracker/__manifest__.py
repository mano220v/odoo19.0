{
    "name": "Module Usage Tracker Dashboard",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Track Odoo module usage time with percentages and dashboard analytics",
    "description": """
Module Usage Tracker Dashboard
==============================
Tracks active browser time per Odoo app/module and shows total usage,
percentage share, user breakdown, recent activity and trend analytics.
""",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "security/ir.model.access.csv",
        "views/module_usage_tracker_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "module_usage_tracker/static/src/js/module_usage_service.js",
            "module_usage_tracker/static/src/js/module_usage_dashboard.js",
            "module_usage_tracker/static/src/xml/module_usage_dashboard.xml",
            "module_usage_tracker/static/src/scss/module_usage_dashboard.scss",
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
