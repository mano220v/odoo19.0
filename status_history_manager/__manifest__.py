{
    'name': 'Field Tracker History Management',
    'version': '19.0.1.1.0',
    'category': 'Inventory/Purchase',
    'summary': 'Track status, price & quantity changes in Purchase, Sales and Inventory with employee audit log',

    'description': """
Status & Changes History Manager
=================================

Track every important change across your business documents — automatically.

**What is recorded:**
- ✅ Status / State Changes
- ✅ Price Changes (Unit Price)
- ✅ Quantity Changes
- ✅ Discount Changes (Sales)

**Tracked on:**
- 📦 Purchase Orders & Lines
- 🛒 Sales Orders & Lines
- 🏭 Inventory / Stock Pickings & Moves

**Each log entry shows:**
- 👤 Employee Name (who made the change)
- 🔄 What changed (Status / Price / Quantity / Discount)
- 📉 From value → 📈 To value
- 📅 Date & Time of change
- 🏷️ Product reference (for line changes)

**Access Control (new in v1.1):**
- 🔒 History User  — can view Change History tab & per-app menus
- 🔑 History Manager — full access including the global All Change History log

**How to use:**
1. Go to **Settings → Users** and assign the *History User* or *History Manager* role.
2. Open any Purchase Order, Sales Order, or Stock Picking and click the
   **"Change History"** tab to see a full audit trail.
3. History Managers can also access the **Change History** top-level menu
   to browse every logged change across all documents.

Perfect for:
- Audit & compliance tracking
- Price negotiation history
- Quantity adjustment logging
- Workflow accountability
    """,

    'author': 'Techie Buddy',
    'website': '',
    'support': 'vsmanoj144@gmail.com',
    'maintainer': 'Techie Buddy',

    'license': 'OPL-1',
    # 'price': 0.00,
    'currency': 'USD',

    'depends': [
        'purchase',
        'sale_management',
        'stock',
        'hr',
    ],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/history_log_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/menu_views.xml',
    ],


    'images': [
        'static/description/banner.png',
        'static/description/screenshot_01_purchase.png',
        'static/description/screenshot_02_sales.png',
        'static/description/screenshot_03_inventory.png',
        'static/description/screenshot_04_global_history.png',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
}
