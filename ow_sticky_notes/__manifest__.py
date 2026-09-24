{
    'name': 'Sticky Notes - Floating Quick Notes Widget',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'A floating sticky-note ball available on every screen — click to open a slide-in notes panel',
    'description': """
Sticky Notes — Floating Quick Notes Widget
===========================================

Brings a Windows-style "Sticky Notes" experience into Odoo:

* A small floating quick-ball is always available, on every backend screen
  (list, form, kanban, settings — everywhere), just like a systray that
  follows you around.
* Click the ball to slide a notes panel in from the right. Click again
  (or the X) to hide it — the ball stays, the panel disappears.
* Keep as many colour-coded sticky notes as you like (yellow, pink, blue,
  green, purple, orange) — not just one.
* Autosaves as you type, no save button required.
* Pin important notes to the top.
* Optionally link a note to the record you currently have open, so it
  resurfaces when you're back on that record.
* Notes are private per user, stored server-side, and follow you across
  devices and sessions.
* Alt+N keyboard shortcut to toggle the panel from anywhere.
* Draggable ball — park it wherever it's out of your way.

Built for Odoo 19.
    """,
    'author': 'Odoo Wings',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings',
    "license": "OPL-1",
    'price': 0.75,
    'currency': 'USD',
    'depends': ['web'],
    'data': [
        'security/sticky_note_security.xml',
        'security/ir.model.access.csv',
        'views/sticky_note_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_sticky_notes/static/src/scss/sticky_notes.scss',
            'ow_sticky_notes/static/src/js/sticky_notes.js',
            'ow_sticky_notes/static/src/xml/sticky_notes.xml',
        ],
    },
    'images': ['static/description/banner.png','static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
