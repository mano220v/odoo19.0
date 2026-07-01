{
    "name": "WooCommerce Connector",
    "version": "19.0.1.0.0",
    "category": "Sales/eCommerce",
    "summary": "Connect WooCommerce with Odoo products, customers, and orders",
    "description": """
WooCommerce Connector
=====================

Synchronize WooCommerce products, customers, and orders with Odoo. The module
includes multi-store configuration, import and export actions, mapping records,
sync logs, and a backend dashboard for operational visibility.
    """,
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    'price': 85.00,
    'currency': 'USD',
    "depends": ["base", "sale_management", "stock", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/woo_mapping_views.xml",
        "views/woo_sync_log_views.xml",
        "views/woo_instance_views.xml",
        "views/woo_dashboard_views.xml",
        "views/woo_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ow_woocommerce_connector/static/src/js/woo_dashboard.js",
            "ow_woocommerce_connector/static/src/xml/woo_dashboard.xml",
            "ow_woocommerce_connector/static/src/scss/woo_dashboard.scss",
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
