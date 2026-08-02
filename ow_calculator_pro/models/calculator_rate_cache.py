# -*- coding: utf-8 -*-
from odoo import fields, models


class CalculatorRateCache(models.Model):
    _name = "calculator.rate.cache"
    _description = "Calculator Pro - Cached Live Currency Rates"
    _rec_name = "base_currency"

    base_currency = fields.Char(string="Base Currency Code", required=True, index=True)
    date = fields.Date(string="Date", required=True, index=True)
    rates_json = fields.Text(string="Rates (JSON)", required=True)

    _sql_constraints = [
        (
            "base_currency_date_uniq",
            "unique(base_currency, date)",
            "Only one live rate snapshot is kept per currency per day.",
        ),
    ]