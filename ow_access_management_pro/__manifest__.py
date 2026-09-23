{
    "name": "Access Management Pro | User Roles & Security",
    "version": "19.0.1.0.0",
    "category": "Administration/Access Rights",
    "summary": "Manage role profiles, model permissions, record rules, menus and field visibility",
    "description": """Build reusable access profiles with users, security groups, model ACLs, record rules, hidden menus, field UI policies and an audit trail.""",
    "author": "Odoo Wings",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Odoo%20Wings",
    "support": "vsmanoj144@gmail.com",
    "license": "OPL-1",
    "price": 39.95,
    "currency": "USD",
    "depends": ["base", "mail", "web"],
    "data": [
        "security/access_security.xml",
        "security/ir.model.access.csv",
        "views/access_profile_views.xml",
        "views/access_audit_views.xml",
        "views/access_menu.xml"
    ],
    "assets": {"web.assets_backend": ["ow_access_management_pro/static/src/scss/access_management.scss"]},
    "images": ["static/description/banner.png", "static/description/icon.png"],
    "installable": True,
    "application": True,
    "auto_install": False
}
