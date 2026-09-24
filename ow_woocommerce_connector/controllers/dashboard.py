import logging
from datetime import datetime, time, timedelta

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

ACTION_METHODS = {
    "sync_all": "action_sync_all",
    "test_connection": "action_test_connection",
    "import_products": "action_import_products",
    "import_customers": "action_import_customers",
    "import_orders": "action_import_orders",
    "export_products": "action_export_products",
}


class WooDashboardController(http.Controller):

    @http.route("/woo_connector/dashboard/data", type="jsonrpc", auth="user")
    def dashboard_data(self):
        Instance = request.env["woo.instance"]
        ProductMap = request.env["woo.product.mapping"]
        PartnerMap = request.env["woo.partner.mapping"]
        OrderMap = request.env["woo.sale.order.mapping"]
        Log = request.env["woo.sync.log"]

        instances = Instance.search([])
        products = ProductMap.search_count([])
        partners = PartnerMap.search_count([])
        orders = OrderMap.search_count([])
        logs = Log.search([], order="create_date desc", limit=20)
        failed_logs = Log.search_count([("state", "=", "failed")])
        success_logs = Log.search_count([("state", "=", "success")])
        total_logs = failed_logs + success_logs
        success_rate = round((success_logs / total_logs) * 100, 1) if total_logs else 100.0

        sync_dates = [date for date in instances.mapped("last_sync_date") if date]
        last_sync = max(sync_dates) if sync_dates else False

        now = fields.Datetime.now()
        today_start = datetime.combine(now.date(), time.min)
        today_syncs = Log.search_count([("create_date", ">=", fields.Datetime.to_string(today_start))])

        # 14-day activity trend (success vs failed counts per day)
        trend = []
        for offset in range(13, -1, -1):
            day_start = today_start - timedelta(days=offset)
            day_end = day_start + timedelta(days=1)
            day_domain = [
                ("create_date", ">=", fields.Datetime.to_string(day_start)),
                ("create_date", "<", fields.Datetime.to_string(day_end)),
            ]
            trend.append({
                "label": day_start.strftime("%b %d"),
                "success": Log.search_count(day_domain + [("state", "=", "success")]),
                "failed": Log.search_count(day_domain + [("state", "=", "failed")]),
            })

        # Operation type breakdown (only non-empty buckets, for the donut chart)
        operation_selection = dict(Log._fields["operation"].selection)
        operations = []
        for op_key, op_label in operation_selection.items():
            count = Log.search_count([("operation", "=", op_key)])
            if count:
                operations.append({"label": op_label, "value": count})

        # Per-instance health snapshot
        instance_data = []
        for instance in instances:
            inst_domain = [("instance_id", "=", instance.id)]
            inst_failed = Log.search_count(inst_domain + [("state", "=", "failed")])
            if not instance.active:
                health = "inactive"
            elif inst_failed:
                health = "error"
            elif not instance.last_sync_date:
                health = "pending"
            else:
                health = "good"
            instance_data.append({
                "id": instance.id,
                "name": instance.name,
                "store_url": instance.store_url,
                "active": instance.active,
                "products": instance.product_mapping_count,
                "customers": instance.partner_mapping_count,
                "orders": instance.order_mapping_count,
                "last_sync": fields.Datetime.to_string(instance.last_sync_date) if instance.last_sync_date else False,
                "failed_logs": inst_failed,
                "health": health,
            })

        return {
            "instances": len(instances),
            "active_instances": len(instances.filtered("active")),
            "products": products,
            "customers": partners,
            "orders": orders,
            "failed_logs": failed_logs,
            "success_logs": success_logs,
            "success_rate": success_rate,
            "today_syncs": today_syncs,
            "last_sync": fields.Datetime.to_string(last_sync) if last_sync else False,
            "trend": trend,
            "operations": operations,
            "instance_data": instance_data,
            "logs": [
                {
                    "id": log.id,
                    "name": log.name,
                    "operation": log.operation,
                    "operation_label": operation_selection.get(log.operation, log.operation),
                    "state": log.state,
                    "message": log.message or "",
                    "instance": log.instance_id.name,
                    "date": fields.Datetime.to_string(log.create_date) if log.create_date else "",
                }
                for log in logs
            ],
        }

    @http.route("/woo_connector/dashboard/quick_action", type="jsonrpc", auth="user")
    def quick_action(self, action, instance_id=None):
        method_name = ACTION_METHODS.get(action)
        if not method_name:
            return {"success": False, "message": "Unknown action."}

        if instance_id:
            instances = request.env["woo.instance"].browse(int(instance_id)).exists()
        else:
            instances = request.env["woo.instance"].search([("active", "=", True)])

        if not instances:
            return {"success": False, "message": "No active store found."}

        try:
            for instance in instances:
                getattr(instance, method_name)()
            return {"success": True}
        except Exception as error:
            _logger.exception("WooCommerce dashboard quick action failed")
            return {"success": False, "message": str(error)}
