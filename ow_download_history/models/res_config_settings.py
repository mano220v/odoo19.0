# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ow_download_history_retention_days = fields.Integer(
        string='Keep Download History For (days)',
        config_parameter='ow_download_history.retention_days',
        default=365,
        help='Download history records older than this many days are '
             'automatically deleted every night. Set to 0 to keep records forever.',
    )
