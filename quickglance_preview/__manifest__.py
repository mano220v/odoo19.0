# -*- coding: utf-8 -*-
{
    "name": "QuickGlance Preview - PDF, Excel & Report Viewer",
    "summary": "Preview PDF reports and Excel/CSV attachments instantly, without downloading first.",
    "description": """
QuickGlance Preview
====================
Stop downloading files just to see what's inside.

* Preview PDF reports (invoices, quotations, any report) in a popup BEFORE
  they are downloaded, with Download / Print actions inside the popup.
* Preview Excel (.xlsx / .xls), CSV and OpenDocument spreadsheet attachments
  directly inside Odoo, with multi-sheet tabs, no LibreOffice/unoconv server
  dependency required.
* Drop-in field widget (`quickglance_preview`) to add a Preview button to any
  Binary field in any view.
* Works on Community and Enterprise.
""",
    "version": "19.0.1.0.0",
    "category": "Productivity/Documents",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    'price': 1.20,
    "depends": ["web", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/ir_attachment_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "quickglance_preview/static/lib/xlsx/xlsx.full.min.js",
            "quickglance_preview/static/src/scss/preview_dialog.scss",
            "quickglance_preview/static/src/js/*.js",
            "quickglance_preview/static/src/xml/*.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}