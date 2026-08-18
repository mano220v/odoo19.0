{
    'name': 'Cache & Storage Manager Pro',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Boost-manager style cache cleaner and storage analyzer',
    'description': """
Odoo Cache & Storage Manager (Premium)
=======================================
- Generate: single-click full scan - cache, storage-by-type, top consumers,
  duplicates, DB size.
- Clear Asset Cache: removes regenerable /web/assets/* bundle attachments
  and clears the ORM/registry (ormcache) in-memory caches.
- Clear Junk: removes orphaned attachments whose parent record no longer
  exists (real disk space recovery, safe - never touches live data).
- Storage by Content Type: Images / Videos / Documents / Audio / Other,
  with a donut chart, each with MB/GB totals and drill-down file lists.
- Drill-down file browser: search, filter by age, per-file or bulk delete,
  with a Junk vs Live-data badge on every row.
- Top Storage Consumers: which models/apps are using the most space.
- Duplicate Record Finder: detects attachments sharing identical file
  content and lets you clean up the extra database rows.
- Auto-Clean Scheduler: optional daily cron that clears asset cache and
  orphaned junk automatically (never touches live or duplicate data).
- Cleanup History: full audit log of every clear action - who, when,
  what, how much freed.
- Excel Export: one-click downloadable report (summary, top models,
  duplicates).
- Database Size overview (PostgreSQL pg_database_size).

Note: Odoo has no single unified "cache size" like a mobile OS. This
module targets the two real, safely-clearable Odoo cache mechanisms
(asset bundles + ormcache) plus genuine junk-file and duplicate-record
cleanup, and gives a full storage breakdown on top.
""",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    'price': 5.00,
    'currency': 'USD',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/cache_manager_menu.xml',
        'views/storage_log_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_cache_manager_pro/static/src/js/attachment_list_dialog.js',
            'ow_cache_manager_pro/static/src/js/duplicate_dialog.js',
            'ow_cache_manager_pro/static/src/js/cache_dashboard.js',
            'ow_cache_manager_pro/static/src/xml/attachment_list_dialog.xml',
            'ow_cache_manager_pro/static/src/xml/duplicate_dialog.xml',
            'ow_cache_manager_pro/static/src/xml/cache_dashboard.xml',
            'ow_cache_manager_pro/static/src/scss/cache_dashboard.scss',
        ],
    },
    'images': ['static/description/icon.png',
             "static/description/banner.png"],
    'installable': True,
    'application': True,
}
