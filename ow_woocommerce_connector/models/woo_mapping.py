from odoo import fields, models


class WooProductMapping(models.Model):
    _name = "woo.product.mapping"
    _description = "WooCommerce Product Mapping"
    _rec_name = "product_tmpl_id"

    instance_id = fields.Many2one("woo.instance", required=True, ondelete="cascade")
    woo_id = fields.Char(required=True, string="WooCommerce ID")
    sku = fields.Char()
    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade")
    last_sync_date = fields.Datetime()

    _woo_product_unique = models.Constraint(
        "unique(instance_id, woo_id)",
        "This WooCommerce product is already mapped for this instance.",
    )


class WooPartnerMapping(models.Model):
    _name = "woo.partner.mapping"
    _description = "WooCommerce Customer Mapping"
    _rec_name = "partner_id"

    instance_id = fields.Many2one("woo.instance", required=True, ondelete="cascade")
    woo_id = fields.Char(required=True, string="WooCommerce ID")
    email = fields.Char()
    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade")
    last_sync_date = fields.Datetime()

    _woo_partner_unique = models.Constraint(
        "unique(instance_id, woo_id)",
        "This WooCommerce customer is already mapped for this instance.",
    )


class WooSaleOrderMapping(models.Model):
    _name = "woo.sale.order.mapping"
    _description = "WooCommerce Sale Order Mapping"
    _rec_name = "sale_order_id"

    instance_id = fields.Many2one("woo.instance", required=True, ondelete="cascade")
    woo_id = fields.Char(required=True, string="WooCommerce ID")
    woo_order_number = fields.Char()
    woo_status = fields.Char()
    sale_order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    last_sync_date = fields.Datetime()

    _woo_order_unique = models.Constraint(
        "unique(instance_id, woo_id)",
        "This WooCommerce order is already mapped for this instance.",
    )
