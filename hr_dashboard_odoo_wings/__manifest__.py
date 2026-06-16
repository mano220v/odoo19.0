{
    "name": "Odoo Wings HR Attendance Dashboard",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Attendances",
    "summary": "Real-time HR attendance dashboard with present, absent, and on-leave counts, live drilldown, and employee analytics",
    "description": """
Real-time HR Attendance Dashboard for Odoo 19.
        Attendance dashboard
        dashboard
        Attendance 
		Hr
Track your workforce instantly with live metrics for:
- Total Employees
- Present Employees
- Absent Employees
- On Leave Employees

Features:
- Live attendance dashboard
- Real-time employee presence analytics
- Clickable drilldown for present, absent, and leave employees
- Today-based attendance calculation
- Auto-refresh dashboard
- Clean and modern UI
- Works with HR, Attendance, and Time Off modules

Best for:
HR dashboard, attendance management, employee presence tracking, leave tracking, workforce analytics, staff monitoring, and Odoo HR 		reporting.
	""",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    'price': 5.00,
    'currency': 'USD',
    'depends': [
        'hr',
        'hr_attendance',
        'hr_holidays',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'data': [
        'views/dashboard_action.xml',
    ],
    'images': [
        'static/description/banner.png',
        'static/description/screenshot_01_main_dashboard.png',
        'static/description/screenshot_02_present_drilldown.png',
        'static/description/screenshot_03_on_leave_drilldown.png',
        'static/description/screenshot_04_absent_drilldown.png',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_dashboard_odoo_wings/static/src/scss/attendance_dashboard.scss',
            'hr_dashboard_odoo_wings/static/src/xml/attendance_dashboard.xml',
            'hr_dashboard_odoo_wings/static/src/js/attendance_dashboard.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
