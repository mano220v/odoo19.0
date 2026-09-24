# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, fields, models


class OwClearDownloadHistoryWizard(models.TransientModel):
    _name = 'ow.clear.download.history.wizard'
    _description = 'Clear Download History'

    older_than_days = fields.Integer(
        string='Delete records older than (days)', default=90, required=True,
        help='All download history records with a download date older than this many days will be permanently deleted.')

    def action_clear(self):
        self.ensure_one()
        cutoff = fields.Datetime.now() - timedelta(days=self.older_than_days)
        records = self.env['ow.download.history'].search([('download_date', '<', cutoff)])
        count = len(records)
        records.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Download History Cleared'),
                'message': _('%s record(s) deleted.') % count,
                'type': 'success',
                'sticky': False,
            },
        }
