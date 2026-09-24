# -*- coding: utf-8 -*-
{
    'name': 'Premium User Login Security',
    'summary': 'Smartphone-style password, PIN, pattern and text-lock sign in',
    'version': '19.0.1.0.10',
    'category': 'Tools',
    'author': 'Odoo Wings',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings',
    'support': 'vsmanoj144@gmail.com',
    'price': 0.15,
    "license": "OPL-1",
    'depends': ['web'],
    'data': [
        'views/res_users_views.xml',
        'views/login_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'ow_premium_login/static/src/scss/premium_login.scss',
        ],
        'web.assets_frontend_lazy': [
            'ow_premium_login/static/src/js/premium_login.js',
        ],
        'web.assets_backend': [
            'ow_premium_login/static/src/scss/premium_login.scss',
            'ow_premium_login/static/src/js/premium_pattern_field.js',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
        'static/description/screenshot_password.png',
        'static/description/screenshot_pattern.png',
        'static/description/screenshot_pin.png',
        'static/description/screenshot_security.png',
        'static/description/screenshot_text_lock.png'
    ],
    'installable': True,
    'application': False,
}
