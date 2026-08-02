# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    calculator_history_enabled = fields.Boolean(
        string="Save Calculation History",
        config_parameter="ow_calculator_pro.history_enabled",
        default=True,
    )
    calculator_decimal_precision = fields.Integer(
        string="Calculator Decimal Precision",
        config_parameter="ow_calculator_pro.decimal_precision",
        default=4,
    )
    calculator_default_theme = fields.Selection(
        [("light", "Light"), ("dark", "Dark")],
        string="Default Theme",
        config_parameter="ow_calculator_pro.default_theme",
        default="light",
    )
    calculator_history_retention_days = fields.Integer(
        string="History Retention (days)",
        config_parameter="ow_calculator_pro.retention_days",
        default=90,
        help="History entries older than this are purged automatically. Set to 0 to keep forever.",
    )
