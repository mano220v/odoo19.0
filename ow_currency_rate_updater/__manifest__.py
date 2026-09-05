# -*- coding: utf-8 -*-
{
    'name': 'Live Currency Rate Updater - Odoo Wings',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Live multi-currency exchange rate updates with a modern real-time dashboard',
    'description': """
Live Currency Rate Updater
===========================
Keep your multi-currency rates fresh automatically, with a dashboard that actually
shows you what's going on instead of a single "Update Now" button.

Key Features
------------
* Live rate fetching from free, key-free providers (Frankfurter / ECB) or any
  custom JSON rate API you configure
* Scheduled automatic background sync with a configurable interval, per company
* One-click manual "Sync Now" with a live progress state
* Modern dashboard: rate cards with up/down trend badges, sparkline history,
  full sortable rate table, and a sync activity log
* Per-company provider, base currency and interval configuration
* Full sync history log with duration, rate count and error detail for auditing
* Writes directly into Odoo's native res.currency.rate model, so Accounting,
  Sales, Purchase and Invoicing all pick up the new rates immediately
""",
    'author': 'Odoo Wings',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings',
    'support': 'vsmanoj144@gmail.com',
    'license': 'OPL-1',
    'depends': ['base', 'base_setup', 'web'],
    'data': [
        'security/ow_currency_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/currency_dashboard_views.xml',
        'views/currency_sync_log_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_currency_rate_updater/static/src/js/*.js',
            'ow_currency_rate_updater/static/src/xml/*.xml',
            'ow_currency_rate_updater/static/src/scss/*.scss',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
    'auto_install': False,
    'price': 0.50,
    'currency': 'EUR',
}
