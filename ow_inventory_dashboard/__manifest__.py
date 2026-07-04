{
    'name': 'Inventory Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Attractive, fully clickable live dashboard for stock levels, transfers, reordering and warehouse activity',
    'description': """
Inventory Dashboard
====================
A premium, fully clickable KPI dashboard for the Inventory app.

Stock levels
------------
* Total storable products, in-stock, low-stock (reordering rules) and out-of-stock counts
* Click any card to open the exact filtered product list

Transfers
----------
* Total open transfers, ready-to-process, late and backorder counts
* Today / Week / Month / All time period filters on every date-based metric
* Incoming, outgoing and internal transfer counters

Operations strip
-----------------
* Scrap tracker
* On-time delivery rate against the scheduled date
* Stock valuation (shown automatically if inventory valuation is enabled)
* Reordering rules counter with one-click access

Insights
--------
* Stock-by-location workload bars, click through to the quants behind any location
* Top products needing reorder, sorted by quantity to order
* 7-day received vs delivered trend chart

Extras
------
* Auto-refresh every 30 seconds, manual refresh button and last-updated indicator
* Colorful, icon-led cards with hover states, consistent with native Odoo styling
* Quick-create button for new transfers
""",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    'price': 3.50,
    'currency': 'USD',
    'depends': ['stock'],
    'data': [
        'views/inventory_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_inventory_dashboard/static/src/js/inventory_dashboard.js',
            'ow_inventory_dashboard/static/src/xml/inventory_dashboard.xml',
            'ow_inventory_dashboard/static/src/scss/inventory_dashboard.scss',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
