from odoo import fields, models


class WooSyncLog(models.Model):
    _name = "woo.sync.log"
    _description = "WooCommerce Sync Log"
    _order = "create_date desc"

    name = fields.Char(required=True)
    instance_id = fields.Many2one("woo.instance", required=True, ondelete="cascade")
    operation = fields.Selection([
        ("test_connection", "Test Connection"),
        ("import_products", "Import Products"),
        ("import_customers", "Import Customers"),
        ("import_orders", "Import Orders"),
        ("export_products", "Export Products"),
        ("sync_all", "Sync All"),
    ], required=True)
    state = fields.Selection([("success", "Success"), ("failed", "Failed")], default="success", required=True)
    message = fields.Text()
