# -*- coding: utf-8 -*-
{
    'name': 'Word Editor – Document Processor',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Full-featured Word Processor inside Odoo with DOCX & PDF export',
    'description': """
Word Editor for Odoo
====================

A professional, full-featured Word Processor built natively inside Odoo.

Key Features
------------
* 📝 Rich Text Editing — Bold, Italic, Underline, Strikethrough, colours, highlights
* 🔤 Typography — Font family, font size, headings (H1–H6), paragraph styles
* 📐 Page Layout — A4 paper simulation with margins, page breaks, zoom control
* ⚙️ Formatting — Alignment, lists (ordered/unordered), indentation, tables, links, images
* 💾 Auto-Save — Documents saved automatically every few seconds while you type
* 📤 Export — One-click export to Microsoft Word (.docx) and PDF
* 🖨️ Print — Print documents directly with proper page formatting
* 📋 Templates — Pre-built templates: Letter, Report, Meeting Notes, Invoice
* 🔍 Find & Replace — Search and replace text anywhere in your document
* 📊 Statistics — Live word count, character count, reading time
* 📁 Document Manager — Full list, kanban, and grid views for all documents
* 🏷️ Tags & Categories — Organise documents with custom tags and statuses
* 💬 Chatter — Comments and activity tracking on every document
* 🔒 Security — Role-based access control (User / Manager)
* 🌐 Multi-company — Compatible with multi-company setups

Technical Requirements
----------------------
To enable DOCX export: ``pip install python-docx beautifulsoup4``

Changelog
---------
* v1.0.0 — Initial release
    """,
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    'price': 1.00,
    'currency': 'USD',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/word_editor_security.xml',
        'security/ir.model.access.csv',
        'report/word_document_report.xml',
        'views/word_document_views.xml',
        'views/menus.xml',
        'data/word_document_template_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'word_editor/static/src/css/word_editor.css',
            'word_editor/static/src/xml/word_editor.xml',
            'word_editor/static/src/js/word_editor.js',
        ],
    },
    'images': [
   	'static/description/banner.gif',
        'static/description/icon.png',
    ],
    'external_dependencies': {
        'python': ['docx', 'bs4'],  # python-docx and beautifulsoup4 — required for native DOCX export
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 100,
}
