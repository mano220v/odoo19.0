{
    'name': 'Warehouse Performance Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Warehouse',
    'summary': 'Warehouse control room for dispatch SLA, exception aging, workload and replenishment',
    'description': """
Warehouse Ops Center is a live control surface for warehouse teams, designed around exceptions and flow instead of dashboard card grids.

Execution control
* Due-within-24-hours queue for arrivals, picks and dispatches
* Overdue operations split into 0–24h, 24–48h and 48h+ aging bands
* Ready-to-execute and needs-reservation workload
* On-time outbound dispatch rate compared with scheduled dates
* One-click drill-down to matching transfer records

Warehouse flow
* Fourteen-day completed receipt, delivery and internal-move trend
* Exact open workload by configured operation type
* Priority queue sorted by overdue work and nearest scheduled transfer
* Optional active picking-batch indicator when batch transfers are installed
* Replenishment watchlist ordered by suggested quantity

Shift tools
* Today, 7-day, 30-day and all-operation windows
* Quick-create receipt, delivery and internal transfer actions
* Automatic refresh every minute and manual refresh
* Responsive dark control-room interface with standard Odoo access rules
""",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    'price': 4.00,
    'currency': 'USD',
    'depends': ['stock'],
    'data': [
        'views/warehouse_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_warehouse_performance_dashboard/static/src/js/warehouse_dashboard.js',
            'ow_warehouse_performance_dashboard/static/src/xml/warehouse_dashboard.xml',
            'ow_warehouse_performance_dashboard/static/src/scss/warehouse_dashboard.scss',
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
