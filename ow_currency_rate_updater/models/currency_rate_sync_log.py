# -*- coding: utf-8 -*-
from odoo import fields, models


class CurrencyRateSyncLog(models.Model):
    _name = 'currency.rate.sync.log'
    _description = 'Currency Rate Sync Log'
    _order = 'create_date desc'
    _rec_name = 'provider'

    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    provider = fields.Selection(
        [('frankfurter', 'Frankfurter.app'), ('ecb', 'European Central Bank'), ('custom', 'Custom API')],
        string='Provider', required=True)
    state = fields.Selection(
        [('success', 'Success'), ('failed', 'Failed')], string='Status', required=True)
    rate_count = fields.Integer(string='Currencies Updated')
    duration = fields.Float(string='Duration (s)')
    message = fields.Char(string='Detail')
    manual = fields.Boolean(string='Manual Trigger', default=False)
