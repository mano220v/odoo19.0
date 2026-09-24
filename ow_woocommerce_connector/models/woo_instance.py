import logging
from urllib.parse import urljoin

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class WooInstance(models.Model):
    _name = "woo.instance"
    _description = "WooCommerce Instance"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    store_url = fields.Char(required=True, help="Example: https://example.com")
    consumer_key = fields.Char(required=True)
    consumer_secret = fields.Char(required=True)
    api_version = fields.Selection(
        [("wc/v3", "WooCommerce REST API v3")],
        default="wc/v3",
        required=True,
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    warehouse_id = fields.Many2one("stock.warehouse", domain="[('company_id', '=', company_id)]")
    pricelist_id = fields.Many2one("product.pricelist")
    auto_confirm_orders = fields.Boolean(default=False)
    last_sync_date = fields.Datetime(readonly=True)
    notes = fields.Text()
    product_mapping_count = fields.Integer(compute="_compute_counts")
    partner_mapping_count = fields.Integer(compute="_compute_counts")
    order_mapping_count = fields.Integer(compute="_compute_counts")
    sync_log_count = fields.Integer(compute="_compute_counts")

    def _compute_counts(self):
        ProductMap = self.env["woo.product.mapping"]
        PartnerMap = self.env["woo.partner.mapping"]
        OrderMap = self.env["woo.sale.order.mapping"]
        Log = self.env["woo.sync.log"]
        for instance in self:
            domain = [("instance_id", "=", instance.id)]
            instance.product_mapping_count = ProductMap.search_count(domain)
            instance.partner_mapping_count = PartnerMap.search_count(domain)
            instance.order_mapping_count = OrderMap.search_count(domain)
            instance.sync_log_count = Log.search_count(domain)

    @staticmethod
    def _clean_url(url):
        return (url or "").rstrip("/") + "/"

    def _endpoint(self, resource):
        self.ensure_one()
        return urljoin(self._clean_url(self.store_url), f"wp-json/{self.api_version}/{resource.lstrip('/')}")

    def _woo_request(self, method, resource, params=None, payload=None):
        self.ensure_one()
        try:
            response = requests.request(
                method,
                self._endpoint(resource),
                auth=(self.consumer_key, self.consumer_secret),
                params=params or {},
                json=payload,
                timeout=45,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            _logger.exception("WooCommerce request failed")
            raise UserError(_("WooCommerce request failed: %s") % error) from error
        if not response.content:
            return {}
        return response.json()

    def _create_log(self, operation, state="success", message=False, name=False):
        self.ensure_one()
        return self.env["woo.sync.log"].create({
            "name": name or dict(self.env["woo.sync.log"]._fields["operation"].selection).get(operation, operation),
            "instance_id": self.id,
            "operation": operation,
            "state": state,
            "message": message,
        })

    def action_test_connection(self):
        for instance in self:
            data = instance._woo_request("GET", "system_status")
            instance._create_log("test_connection", message=_("Connected to WooCommerce store successfully."))
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Successful"),
                    "message": _("Store status received from %s.") % (data.get("environment", {}).get("home_url") or instance.store_url),
                    "type": "success",
                    "sticky": False,
                },
            }
        return False

    def action_import_products(self):
        for instance in self:
            count = instance._import_products()
            instance._mark_synced()
            instance._create_log("import_products", message=_("Imported or updated %s products.") % count)
        return self._reload_notification(_("Product import completed."))

    def action_import_customers(self):
        for instance in self:
            count = instance._import_customers()
            instance._mark_synced()
            instance._create_log("import_customers", message=_("Imported or updated %s customers.") % count)
        return self._reload_notification(_("Customer import completed."))

    def action_import_orders(self):
        for instance in self:
            count = instance._import_orders()
            instance._mark_synced()
            instance._create_log("import_orders", message=_("Imported or updated %s orders.") % count)
        return self._reload_notification(_("Order import completed."))

    def action_export_products(self):
        for instance in self:
            count = instance._export_products()
            instance._mark_synced()
            instance._create_log("export_products", message=_("Exported or updated %s products.") % count)
        return self._reload_notification(_("Product export completed."))

    def action_sync_all(self):
        for instance in self:
            products = instance._import_products()
            customers = instance._import_customers()
            orders = instance._import_orders()
            instance._mark_synced()
            instance._create_log(
                "sync_all",
                message=_("Synchronized %s products, %s customers, and %s orders.") % (products, customers, orders),
            )
        return self._reload_notification(_("WooCommerce synchronization completed."))

    def _mark_synced(self):
        self.write({"last_sync_date": fields.Datetime.now()})

    def _reload_notification(self, message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("WooCommerce"), "message": message, "type": "success", "sticky": False},
        }

    def _paged_get(self, resource, params=None, limit_pages=10):
        records = []
        page = 1
        while page <= limit_pages:
            page_params = dict(params or {}, page=page, per_page=100)
            batch = self._woo_request("GET", resource, params=page_params)
            if not batch:
                break
            records.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return records

    def _import_products(self):
        self.ensure_one()
        mapping_model = self.env["woo.product.mapping"]
        count = 0
        for item in self._paged_get("products"):
            woo_id = str(item.get("id"))
            if not woo_id:
                continue
            vals = {
                "name": item.get("name") or _("WooCommerce Product"),
                "default_code": item.get("sku") or False,
                "list_price": float(item.get("regular_price") or item.get("price") or 0.0),
                "sale_ok": True,
                "purchase_ok": False,
                "company_id": self.company_id.id,
            }
            mapping = mapping_model.search([("instance_id", "=", self.id), ("woo_id", "=", woo_id)], limit=1)
            if mapping:
                mapping.product_tmpl_id.write(vals)
                product = mapping.product_tmpl_id
            else:
                product = self.env["product.template"].create(vals)
                mapping_model.create({"instance_id": self.id, "woo_id": woo_id, "product_tmpl_id": product.id, "sku": item.get("sku")})
            count += 1
        return count

    def _import_customers(self):
        self.ensure_one()
        mapping_model = self.env["woo.partner.mapping"]
        count = 0
        for item in self._paged_get("customers"):
            woo_id = str(item.get("id"))
            if not woo_id:
                continue
            first = item.get("first_name") or ""
            last = item.get("last_name") or ""
            vals = {
                "name": (f"{first} {last}".strip() or item.get("username") or item.get("email") or _("WooCommerce Customer")),
                "email": item.get("email") or False,
                "phone": item.get("billing", {}).get("phone") or False,
                "customer_rank": 1,
                "company_id": self.company_id.id,
            }
            mapping = mapping_model.search([("instance_id", "=", self.id), ("woo_id", "=", woo_id)], limit=1)
            if mapping:
                mapping.partner_id.write(vals)
            else:
                partner = self.env["res.partner"].create(vals)
                mapping_model.create({"instance_id": self.id, "woo_id": woo_id, "partner_id": partner.id, "email": vals["email"]})
            count += 1
        return count

    def _import_orders(self):
        self.ensure_one()
        mapping_model = self.env["woo.sale.order.mapping"]
        count = 0
        for item in self._paged_get("orders"):
            woo_id = str(item.get("id"))
            if not woo_id or mapping_model.search_count([("instance_id", "=", self.id), ("woo_id", "=", woo_id)]):
                continue
            partner = self._partner_from_order(item)
            order_vals = {
                "partner_id": partner.id,
                "company_id": self.company_id.id,
                "origin": item.get("number") and _("WooCommerce Order #%s") % item.get("number"),
                "client_order_ref": item.get("number"),
                "pricelist_id": (self.pricelist_id or partner.property_product_pricelist).id,
                "warehouse_id": self.warehouse_id.id if self.warehouse_id else False,
            }
            sale_order = self.env["sale.order"].create(order_vals)
            for line in item.get("line_items", []):
                product = self._product_from_order_line(line)
                self.env["sale.order.line"].create({
                    "order_id": sale_order.id,
                    "product_id": product.id,
                    "name": line.get("name") or product.display_name,
                    "product_uom_qty": float(line.get("quantity") or 1.0),
                    "price_unit": float(line.get("price") or 0.0),
                })
            if self.auto_confirm_orders:
                sale_order.action_confirm()
            mapping_model.create({
                "instance_id": self.id,
                "woo_id": woo_id,
                "sale_order_id": sale_order.id,
                "woo_order_number": item.get("number"),
                "woo_status": item.get("status"),
            })
            count += 1
        return count

    def _partner_from_order(self, order):
        email = order.get("billing", {}).get("email") or order.get("shipping", {}).get("email")
        customer_id = order.get("customer_id")
        mapping = False
        if customer_id:
            mapping = self.env["woo.partner.mapping"].search([
                ("instance_id", "=", self.id),
                ("woo_id", "=", str(customer_id)),
            ], limit=1)
        if mapping:
            return mapping.partner_id
        partner = self.env["res.partner"].search([("email", "=", email)], limit=1) if email else False
        if not partner:
            billing = order.get("billing", {})
            name = f"{billing.get('first_name') or ''} {billing.get('last_name') or ''}".strip()
            partner = self.env["res.partner"].create({
                "name": name or email or _("WooCommerce Guest"),
                "email": email,
                "phone": billing.get("phone"),
                "customer_rank": 1,
                "company_id": self.company_id.id,
            })
        if customer_id:
            self.env["woo.partner.mapping"].create({
                "instance_id": self.id,
                "woo_id": str(customer_id),
                "partner_id": partner.id,
                "email": email,
            })
        return partner

    def _product_from_order_line(self, line):
        woo_product_id = str(line.get("product_id") or "")
        mapping = self.env["woo.product.mapping"].search([
            ("instance_id", "=", self.id),
            ("woo_id", "=", woo_product_id),
        ], limit=1)
        if mapping:
            return mapping.product_tmpl_id.product_variant_id
        product = self.env["product.product"].create({
            "name": line.get("name") or _("WooCommerce Product"),
            "default_code": line.get("sku") or False,
            "list_price": float(line.get("price") or 0.0),
            "company_id": self.company_id.id,
        })
        if woo_product_id:
            self.env["woo.product.mapping"].create({
                "instance_id": self.id,
                "woo_id": woo_product_id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "sku": line.get("sku"),
            })
        return product

    def _export_products(self):
        self.ensure_one()
        mappings = self.env["woo.product.mapping"].search([("instance_id", "=", self.id)])
        count = 0
        for mapping in mappings:
            product = mapping.product_tmpl_id
            payload = {
                "name": product.name,
                "sku": mapping.sku or product.default_code or "",
                "regular_price": str(product.list_price or 0.0),
            }
            if mapping.woo_id:
                self._woo_request("PUT", f"products/{mapping.woo_id}", payload=payload)
            else:
                result = self._woo_request("POST", "products", payload=payload)
                mapping.woo_id = str(result.get("id"))
            count += 1
        return count

    @api.constrains("store_url")
    def _check_store_url(self):
        for instance in self:
            if instance.store_url and not instance.store_url.startswith(("http://", "https://")):
                raise ValidationError(_("Store URL must start with http:// or https://."))
