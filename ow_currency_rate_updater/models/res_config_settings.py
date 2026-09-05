# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ow_currency_auto_update = fields.Boolean(
        related='company_id.ow_currency_auto_update', readonly=False)
    ow_currency_provider = fields.Selection(
        related='company_id.ow_currency_provider', readonly=False)
    ow_currency_update_interval = fields.Selection(
        related='company_id.ow_currency_update_interval', readonly=False)
    ow_currency_custom_api_url = fields.Char(
        related='company_id.ow_currency_custom_api_url', readonly=False)
    ow_currency_custom_api_key = fields.Char(
        related='company_id.ow_currency_custom_api_key', readonly=False)
    ow_currency_last_sync_date = fields.Datetime(related='company_id.ow_currency_last_sync_date')
    ow_currency_last_sync_state = fields.Selection(related='company_id.ow_currency_last_sync_state')
    ow_currency_base_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Base Currency', readonly=True,
        help="Rates are always fetched relative to this currency. To change it, "
             "update your company's currency in Accounting/Invoicing Settings.")
