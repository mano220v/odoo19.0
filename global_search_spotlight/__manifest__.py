{
    'name': 'Global Search Spotlight',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Spotlight / Cmd+K style global quick-search for the Odoo backend',
    'description': """
Global Search Spotlight
========================
Adds a Spotlight (macOS) / Cmd+K (Slack) style global search overlay to the
Odoo backend.

Features
--------
* Press ``Ctrl+K`` (``Cmd+K`` on Mac) anywhere in the backend, or click the
  magnifying-glass icon in the systray, to open a centered search overlay.
* Debounced, as-you-type search across Contacts, Sales Orders and Products.
* Results are grouped by category and fully respect the current user's
  access rights and record rules (no ``sudo()`` is used anywhere).
* Keyboard navigable (Arrow keys + Enter) and click-to-open, both of which
  redirect straight to the record's form view via the ``action`` service.

Notes
-----
Odoo's own web client also binds ``Ctrl+K`` to its built-in Command Palette
(the app switcher / "Go to" search). Depending on your version/config the
two may compete for the same shortcut - see the comment at the top of
``static/src/js/global_search.js`` for how to resolve this if it happens.
""",
    'author': 'Odoo Wings',
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    'support': 'vsmanoj144@gmail.com',
    'license': 'LGPL-3',
    # Only 'base' + 'web' are required. product.template / sale.order are
    # probed for at runtime (see models/global_search.py) so this module
    # installs cleanly even on a database without Sales/Inventory installed.
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'global_search_spotlight/static/src/scss/global_search.scss',
            'global_search_spotlight/static/src/js/global_search.js',
            'global_search_spotlight/static/src/xml/global_search.xml',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
