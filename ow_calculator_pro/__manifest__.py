{
    "name": "Calculator Pro",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Premium all-in-one calculator suite for Odoo: standard, scientific, "
               "currency, unit, loan/EMI, date, BMI and discount/tax calculators "
               "with history, favorites and a live usage dashboard",
    "description": """
        Calculator Pro
        ===============
        A premium, all-in-one calculator workspace built natively into Odoo. Calculator
        Pro brings eight dedicated calculators, personal history and favorites, and a
        live usage dashboard into one polished backend app - no external tool, no
        separate login, no subscription.

        Included calculators
        ---------------------
        * Standard calculator with memory (M+/M-/MR/MC)
        * Scientific calculator (trigonometry, logarithms, powers, factorials, constants)
        * Currency converter, powered by Odoo's own currency rates
        * Unit converter (length, weight, temperature, area, volume, speed, time, data)
        * Loan / EMI calculator with a 12-month amortization preview
        * Date calculator (difference between two dates, in years/months/days)
        * BMI calculator (metric and imperial)
        * Discount & tax calculator

        Productivity features
        -----------------------
        * Personal calculation history, auto-logged per user
        * Favorites - save and reuse frequent expressions
        * Light and dark theme
        * Keyboard support for the standard and scientific calculators
        * One-click copy to clipboard
        * Configurable decimal precision, history retention and default theme
        * Automatic daily cleanup of old history entries
        * Runs entirely on native Odoo security - internal users only, no external
        service required
            """,
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    "price": 8.50,
    "currency": "USD",
    "depends": ["base", "web", "mail", "base_setup"],
    "data": [
        "security/calculator_security.xml",
        "security/ir.model.access.csv",
        "views/calculator_history_views.xml",
        "views/calculator_favorite_views.xml",
        "views/res_config_settings_views.xml",
        "views/calculator_menus.xml",
        "data/calculator_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ow_calculator_pro/static/src/scss/calculator_app.scss",
            "ow_calculator_pro/static/src/js/calculator_engine.js",
            "ow_calculator_pro/static/src/js/unit_data.js",
            "ow_calculator_pro/static/src/js/calculator_app.js",
            "ow_calculator_pro/static/src/xml/calculator_app.xml",
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
