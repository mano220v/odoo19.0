# -*- coding: utf-8 -*-
import logging
import time
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .currency_providers import fetch_rates, CurrencyProviderError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    ow_currency_auto_update = fields.Boolean(
        string='Auto-Update Currency Rates', default=True,
        help="When enabled, rates are refreshed automatically in the background "
             "on the interval configured below.")
    ow_currency_provider = fields.Selection(
        [('frankfurter', 'Frankfurter.app (free, no key, ECB data)'),
         ('ecb', 'European Central Bank (official feed)'),
         ('custom', 'Custom API')],
        string='Rate Provider', default='frankfurter', required=True)
    ow_currency_update_interval = fields.Selection(
        [('1', 'Every hour'),
         ('3', 'Every 3 hours'),
         ('6', 'Every 6 hours'),
         ('12', 'Every 12 hours'),
         ('24', 'Once a day')],
        string='Update Interval', default='6', required=True)
    ow_currency_custom_api_url = fields.Char(
        string='Custom API URL',
        help="A JSON endpoint returning {\"rates\": {\"USD\": 1.08, ...}}")
    ow_currency_custom_api_key = fields.Char(string='Custom API Key')

    ow_currency_last_sync_date = fields.Datetime(string='Last Sync', readonly=True)
    ow_currency_last_sync_state = fields.Selection(
        [('none', 'Never Synced'), ('success', 'Success'), ('failed', 'Failed')],
        string='Last Sync Status', default='none', readonly=True)
    ow_currency_last_sync_message = fields.Char(string='Last Sync Message', readonly=True)
    ow_currency_last_sync_count = fields.Integer(string='Currencies Updated', readonly=True)

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------
    def action_sync_currency_rates_now(self):
        """Manual sync, triggered from the dashboard button. Returns a
        client notification so the UI can show success/failure immediately.
        """
        self.ensure_one()
        result = self._sync_currency_rates(manual=True)
        if result['state'] == 'success':
            message = _("%s exchange rates updated from %s.") % (
                result['count'], result['provider_label'])
            sticky = False
            rtype = 'success'
        else:
            message = result['message']
            sticky = True
            rtype = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Currency Rate Sync'),
                'message': message,
                'type': rtype,
                'sticky': sticky,
            },
        }

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------
    @api.model
    def _cron_sync_currency_rates(self):
        companies = self.sudo().search([('ow_currency_auto_update', '=', True)])
        now = fields.Datetime.now()
        for company in companies:
            interval_hours = int(company.ow_currency_update_interval or '6')
            if company.ow_currency_last_sync_date:
                due_at = company.ow_currency_last_sync_date + timedelta(hours=interval_hours)
                if now < due_at:
                    continue
            try:
                company._sync_currency_rates(manual=False)
            except Exception:  # noqa: BLE001
                _logger.exception("Currency rate cron sync failed for company %s", company.display_name)

    # ------------------------------------------------------------------
    # Core sync logic
    # ------------------------------------------------------------------
    def _sync_currency_rates(self, manual=False):
        self.ensure_one()
        Log = self.env['currency.rate.sync.log'].sudo()
        Rate = self.env['res.currency.rate'].sudo()
        Currency = self.env['res.currency'].sudo()

        start = time.time()
        base_code = self.currency_id.name
        provider = self.ow_currency_provider

        try:
            rates, meta = fetch_rates(
                provider,
                base_code,
                custom_url=self.ow_currency_custom_api_url,
                custom_api_key=self.ow_currency_custom_api_key,
            )
        except CurrencyProviderError as e:
            duration = time.time() - start
            self.write({
                'ow_currency_last_sync_date': fields.Datetime.now(),
                'ow_currency_last_sync_state': 'failed',
                'ow_currency_last_sync_message': str(e),
                'ow_currency_last_sync_count': 0,
            })
            Log.create({
                'company_id': self.id,
                'provider': provider,
                'state': 'failed',
                'rate_count': 0,
                'duration': duration,
                'message': str(e),
                'manual': manual,
            })
            return {'state': 'failed', 'message': str(e)}

        active_currencies = Currency.search([('active', '=', True)])
        today = fields.Date.context_today(self)
        updated = 0
        for currency in active_currencies:
            code = currency.name
            if code == base_code:
                continue
            if code not in rates or not rates[code]:
                continue
            existing = Rate.search([
                ('currency_id', '=', currency.id),
                ('name', '=', today),
                ('company_id', '=', self.id),
            ], limit=1)
            vals = {
                'currency_id': currency.id,
                'name': today,
                'rate': rates[code],
                'company_id': self.id,
            }
            if existing:
                existing.write({'rate': rates[code]})
            else:
                Rate.create(vals)
            updated += 1

        duration = time.time() - start
        provider_label = meta.get('provider_label', provider)
        self.write({
            'ow_currency_last_sync_date': fields.Datetime.now(),
            'ow_currency_last_sync_state': 'success',
            'ow_currency_last_sync_message': _("%s currencies updated") % updated,
            'ow_currency_last_sync_count': updated,
        })
        Log.create({
            'company_id': self.id,
            'provider': provider,
            'state': 'success',
            'rate_count': updated,
            'duration': duration,
            'message': _("Source date: %s") % (meta.get('source_date') or today),
            'manual': manual,
        })
        return {'state': 'success', 'count': updated, 'provider_label': provider_label}
