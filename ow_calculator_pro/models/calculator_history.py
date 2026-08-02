# -*- coding: utf-8 -*-
import json
import logging
import urllib.request
from datetime import timedelta
from urllib.error import URLError

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

CALCULATOR_TYPES = [
    ("standard", "Standard"),
    ("scientific", "Scientific"),
    ("currency", "Currency Converter"),
    ("unit", "Unit Converter"),
    ("loan", "Loan / EMI"),
    ("date", "Date Calculator"),
    ("bmi", "BMI"),
    ("discount", "Discount / Tax"),
]

# Free, keyless, daily-updated exchange rate service (base currency inserted).
LIVE_RATE_API_URL = "https://open.er-api.com/v6/latest/%s"


class CalculatorHistory(models.Model):
    _name = "calculator.history"
    _description = "Calculator History"
    _order = "create_date desc"
    _rec_name = "expression"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        required=True,
        index=True,
        ondelete="cascade",
    )
    category = fields.Selection(
        CALCULATOR_TYPES,
        string="Calculator Type",
        required=True,
        default="standard",
        index=True,
    )
    expression = fields.Char(string="Expression", required=True)
    result = fields.Char(string="Result", required=True)
    note = fields.Char(string="Note")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "%s = %s" % (rec.expression, rec.result)))
        return result

    @api.model
    def action_clear_my_history(self):
        """Delete every history entry belonging to the current user."""
        self.search([("user_id", "=", self.env.uid)]).unlink()
        return True

    @api.model
    def get_currency_rate(self, from_currency_id, to_currency_id):
        """Return today's conversion rate between two currencies.

        Tries a free, daily-updated public exchange-rate service first
        (cached for the rest of the day so we don't call it on every
        conversion). If that service can't be reached - no internet on
        the server, DNS/firewall block, etc. - falls back to Odoo's own
        res.currency rate tables so the tool still works.

        Returns a dict: {"rate": float, "source": "live" | "odoo"}.
        """
        from_currency = self.env["res.currency"].browse(from_currency_id)
        to_currency = self.env["res.currency"].browse(to_currency_id)

        live_rate = self._get_live_currency_rate(from_currency.name, to_currency.name)
        if live_rate is not None:
            return {"rate": live_rate, "source": "live"}

        fallback_rate = self.env["res.currency"]._get_conversion_rate(
            from_currency, to_currency, self.env.company, fields.Date.today()
        )
        return {"rate": fallback_rate, "source": "odoo"}

    def _get_live_currency_rate(self, from_code, to_code):
        """Return today's rate for from_code -> to_code, or None if the
        live service could not be reached / didn't know that currency."""
        if from_code == to_code:
            return 1.0

        rates = self._get_live_rates_for_base(from_code)
        if not rates:
            return None
        return rates.get(to_code)

    def _get_live_rates_for_base(self, base_code):
        """Return {currency_code: rate, ...} for the given base currency,
        for today, using a same-day cache to avoid repeated HTTP calls."""
        today = fields.Date.context_today(self)
        Cache = self.env["calculator.rate.cache"].sudo()

        cached = Cache.search(
            [("base_currency", "=", base_code), ("date", "=", today)], limit=1
        )
        if cached:
            try:
                return json.loads(cached.rates_json)
            except ValueError:
                cached.unlink()  # corrupted cache row, refetch below

        rates = self._fetch_live_rates(base_code)
        if not rates:
            return None

        # Best-effort cache write; never let this break the conversion.
        try:
            existing = Cache.search(
                [("base_currency", "=", base_code), ("date", "=", today)], limit=1
            )
            if existing:
                existing.rates_json = json.dumps(rates)
            else:
                Cache.create(
                    {
                        "base_currency": base_code,
                        "date": today,
                        "rates_json": json.dumps(rates),
                    }
                )
            # Trim old snapshots so this table never grows unbounded.
            old = Cache.search([("date", "<", today - timedelta(days=7))])
            old.unlink()
        except Exception:  # noqa: BLE001 - caching is optional, never fatal
            _logger.warning("Calculator Pro: could not cache live rates", exc_info=True)

        return rates

    def _fetch_live_rates(self, base_code):
        """Call the live exchange-rate API. Returns a rates dict or None."""
        try:
            request = urllib.request.Request(
                LIVE_RATE_API_URL % base_code,
                headers={"User-Agent": "Odoo-CalculatorPro/1.0"},
            )
            with urllib.request.urlopen(request, timeout=6) as response:
                data = json.loads(response.read().decode())
        except (URLError, TimeoutError, OSError, ValueError):
            _logger.warning(
                "Calculator Pro: live currency rate fetch failed for %s, "
                "falling back to Odoo's stored rates",
                base_code,
                exc_info=True,
            )
            return None

        if data.get("result") != "success":
            return None
        return data.get("rates") or {}

    @api.model
    def _cron_purge_old_history(self):
        """Scheduled action: purge history older than the configured
        retention window (0 = keep forever)."""
        icp = self.env["ir.config_parameter"].sudo()
        retention_days = int(icp.get_param("ow_calculator_pro.retention_days", default=90))
        if retention_days > 0:
            cutoff = fields.Datetime.now() - timedelta(days=retention_days)
            self.sudo().search([("create_date", "<", cutoff)]).unlink()