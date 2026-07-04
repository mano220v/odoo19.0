{
    'name': 'Manufacturing Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Colorful clickable dashboard for Manufacturing Orders, Job Orders and shop-floor operations',
    'description': """
Manufacturing Dashboard
========================
A premium, fully clickable, colorful KPI dashboard for the Manufacturing app.

Features
--------
* Live counts for Manufacturing Orders and Job (Work) Orders, broken down by status
* Click any KPI card to instantly open the underlying filtered records
* Today / Week / Month / All time period filters
* Material shortage tracker - orders missing components, pulled from component availability
* Scrap tracker linked to manufacturing orders
* On-time completion rate, computed against each order's planned finish date
* Bills of materials count with one click through to the BoM list
* Quality checks and maintenance requests widgets (shown automatically if those apps are installed)
* Work center workload bars - click a work center to see its open job orders
* Top delayed manufacturing orders list with one-click drill-down to the record
* 7-day completed-orders trend chart
* Quick-create button for new manufacturing orders
* Auto-refresh every 30 seconds, plus a manual refresh button and last-updated indicator
* Colorful, icon-led cards with native Odoo styling, hover states and status badges
""",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    'price': 3.50,
    'currency': 'USD',
    'depends': ['mrp'],
    'data': [
        'views/manufacturing_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_manufacturing_dashboard/static/src/js/manufacturing_dashboard.js',
            'ow_manufacturing_dashboard/static/src/xml/manufacturing_dashboard.xml',
            'ow_manufacturing_dashboard/static/src/scss/manufacturing_dashboard.scss',
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
