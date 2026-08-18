{
    'name': 'Cache & Storage Manager',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Boost-manager style cache cleaner and storage analyzer',
    'description': """
Odoo Cache & Storage Manager
=============================
- Generate: scans ir.attachment table and shows current usage.
- Clear Asset Cache: removes regenerable /web/assets/* bundle attachments
  and clears the ORM/registry (ormcache) in-memory caches.
- Clear Junk: removes orphaned attachments whose parent record no longer
  exists (real disk space recovery, safe - never touches live data).
- Storage by Content Type: Images / Videos / Documents / Audio / Other,
  each with MB/GB totals, like a mobile "device manager" view.
- Shows freed space (before/after) on every clear action.

Note: Odoo has no single unified "cache size" like a mobile OS. This
module targets the two real, safely-clearable Odoo cache mechanisms
(asset bundles + ormcache) plus genuine junk-file cleanup, and gives a
full storage breakdown on top so you can see where filestore space is
actually going.
""",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/cache_manager_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_cache_manager/static/src/js/attachment_list_dialog.js',
            'ow_cache_manager/static/src/js/cache_dashboard.js',
            'ow_cache_manager/static/src/xml/attachment_list_dialog.xml',
            'ow_cache_manager/static/src/xml/cache_dashboard.xml',
            'ow_cache_manager/static/src/scss/cache_dashboard.scss',
        ],
    },
    'images': ['static/description/icon.png'],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
