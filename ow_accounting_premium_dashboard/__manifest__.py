# -*- coding: utf-8 -*-
{
    "name": "Premium Accounting Dashboard",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "An executive finance dashboard for income, expenses, cash, receivables and payables",
    "description": """
Premium Accounting Dashboard
============================
A polished accounting overview built for Odoo 19.

Highlights
----------
* Revenue, vendor costs and net invoiced for the selected period
* Open receivables and payables in company currency
* Current cash and bank balances from posted journal items
* Six-month income versus expense trend
* Overdue customer invoices and upcoming vendor bills
* Recent invoice and bill activity with direct drill-down
* Period filters for month, quarter, year and all time
* Automatic refresh and responsive layout
    """,
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    "depends": ["account", "web"],
    "data": [
        "views/accounting_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ow_accounting_premium_dashboard/static/src/js/accounting_dashboard.js",
            "ow_accounting_premium_dashboard/static/src/xml/accounting_dashboard.xml",
            "ow_accounting_premium_dashboard/static/src/scss/accounting_dashboard.scss",
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
        "static/description/screenshots/screenshot_01_finance_studio.png",
        "static/description/screenshots/screenshot_02_performance_follow_up.png",
        "static/description/screenshots/screenshot_03_recent_activity.png",
        "static/description/screenshots/screenshot_04_invoice_list.png",
    ],
    "price": 2.58,
    "currency": "USD",
    "installable": True,
    "application": True,
    "auto_install": False,
}
