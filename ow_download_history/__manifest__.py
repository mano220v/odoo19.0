# -*- coding: utf-8 -*-
{
    'name': 'Download History Manager',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Track who downloaded which file and when — a complete download audit trail',
    'description': """
Download History Manager
=========================
Know exactly **who downloaded what, and when** — across your entire Odoo
system.

This module silently tracks every file download that happens through
Odoo's standard download channels and logs it to a searchable, filterable
history:

* **Attachments** — any document downloaded from the Documents app,
  chatter, or any "Download" link/button.
* **Reports** — every PDF / XLSX report a user prints or downloads
  (invoices, quotations, payslips, custom reports, etc.).
* **Data exports** — spreadsheet exports (XLSX/CSV) generated from list
  views.

Key Features
------------
* Automatic, silent logging — no changes needed to existing workflows.
* Records the user, exact date/time, file name, file size, mime type,
  IP address, and the source record the file came from.
* One click to jump back to the source record from a history line.
* Dashboard with pivot & graph views to analyze download activity by
  user, date, or file type.
* Configurable automatic cleanup of old history (data retention policy).
* Manual "Clear History" wizard for admins.
* Two access levels: users can optionally see their own download
  history; managers see everything.

Perfect for compliance, security audits, and understanding how your
documents and reports are actually being used.
""",
    'author': 'Odoo Wings',
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    'support': 'vsmanoj144@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/download_history_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'wizard/clear_history_wizard_views.xml',
        'views/download_history_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
