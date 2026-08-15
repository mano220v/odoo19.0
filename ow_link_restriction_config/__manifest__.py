{
    'name': 'ow - Configurable Internal Link Restriction',
    'version': '19.0.1.0.1',
    'summary': 'Pick specific models to disable the Many2one "internal link" '
               'open-record navigation on, for Form and List views only.',
    'description': """
Configurable Internal Link Restriction
=======================================

Lets an admin pick which models should have their Many2one fields'
"Internal link" click-through (the hover arrow / clickable value that
opens the linked record's form) disabled.

- Restriction applies only to that model's Form and List views.
- Kanban views are NEVER affected, regardless of configuration.
- Toggle a model's "Active" flag to turn its restriction on/off without
  deleting the config entry.

Configure under: Ow Tools > Internal Link Restrictions
(visible to users in the Settings / Technical Features group).

IMPORTANT NOTES
---------------
* This is a client-side UI restriction only. It does NOT change record
  access rights (ir.model.access.csv) or record rules (ir.rule). A user
  who has read access to a restricted model's records can still reach
  them through search, another menu, a report, etc. Use ir.rule for
  actual data-level security.
* The restricted-model list is loaded once when the session starts
  (page load / login). After adding, removing, or toggling a model,
  users must refresh their browser tab for the change to apply.
""",
    'category': 'Tools',
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    'depends': ['web', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/link_restriction_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_link_restriction_config/static/src/js/restrict_many2one_link.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
