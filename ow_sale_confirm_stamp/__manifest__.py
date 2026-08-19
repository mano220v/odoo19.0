# -*- coding: utf-8 -*-
{
    'name': 'Sale Order Confirmed Stamp',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Show a green confirmed stamp with confirmation date on sale orders',
    'description': """
Sale Order Confirmed Stamp
==========================

Show a clear green confirmation stamp on confirmed sale orders.

Features
--------
* Adds a polished stamp in the top-right area of the sale order form.
* Displays the company name around the stamp circle.
* Shows SALE CONFIRMED and the confirmation date inside the stamp.
* Stores the actual confirmation date when the quotation is confirmed.
* Works automatically for orders in Sales Order or Locked state.
* Lightweight module with no menus, no configuration and no data migration.
    """,
    'author': 'Odoo Wings',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings',
    'support': 'vsmanoj144@gmail.com',
    'maintainer': 'Odoo Wings',
    'license': 'LGPL-3',
    'price': 1.00,
    'currency': 'USD',
    'depends': [
        'sale_management',
    ],
    'data': [
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ow_sale_confirm_stamp/static/src/scss/sale_confirm_stamp.scss',
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
