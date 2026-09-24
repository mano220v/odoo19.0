# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class OwDownloadHistory(models.Model):
    _name = 'ow.download.history'
    _description = 'Download History'
    _order = 'download_date desc, id desc'
    _rec_name = 'file_name'

    file_name = fields.Char(string='File Name', required=True, index=True)
    file_type = fields.Selection([
        ('attachment', 'Attachment'),
        ('image', 'Image'),
        ('report', 'Report'),
        ('export', 'Data Export'),
        ('other', 'Other'),
    ], string='Source Type', required=True, default='attachment', index=True)
    mimetype = fields.Char(string='Mime Type')
    file_size = fields.Integer(string='File Size (bytes)')
    file_size_human = fields.Char(string='File Size', compute='_compute_file_size_human')
    user_id = fields.Many2one(
        'res.users', string='Downloaded By', required=True,
        index=True, default=lambda self: self.env.uid, ondelete='cascade')
    download_date = fields.Datetime(
        string='Download Date', required=True, default=fields.Datetime.now, index=True)
    ip_address = fields.Char(string='IP Address')
    res_model = fields.Char(string='Source Model', index=True)
    res_id = fields.Integer(string='Source Record ID')
    res_name = fields.Char(string='Source Record')
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', ondelete='set null')
    report_id = fields.Many2one('ir.actions.report', string='Report', ondelete='set null')
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)

    @api.depends('file_size')
    def _compute_file_size_human(self):
        for rec in self:
            size = float(rec.file_size or 0)
            human = f"{int(size)} B"
            for unit in ('KB', 'MB', 'GB', 'TB'):
                if size < 1024.0:
                    break
                size /= 1024.0
                human = f"{size:.1f} {unit}"
            rec.file_size_human = human

    def action_open_source_record(self):
        """Jump back to the record the downloaded file belongs to."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        if self.res_model not in self.env:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def log_download(self, file_name, file_type='attachment', mimetype=False, file_size=0,
                      res_model=False, res_id=False, res_name=False,
                      attachment_id=False, report_id=False, request=None):
        """Create a download history record.

        Always runs as sudo so the log is written regardless of the
        downloading user's access rights on this model.
        """
        ip_address = False
        if request is not None:
            try:
                ip_address = request.httprequest.environ.get('REMOTE_ADDR')
            except Exception:
                ip_address = False
        vals = {
            'file_name': file_name or 'unknown',
            'file_type': file_type or 'other',
            'mimetype': mimetype,
            'file_size': file_size or 0,
            'res_model': res_model or False,
            'res_id': res_id or False,
            'res_name': res_name or False,
            'attachment_id': attachment_id or False,
            'report_id': report_id or False,
            'ip_address': ip_address,
            'user_id': self.env.uid,
        }
        return self.sudo().create(vals)

    @api.model
    def _cron_cleanup_old_history(self):
        """Delete history records older than the configured retention period."""
        icp = self.env['ir.config_parameter'].sudo()
        retention_days = int(icp.get_param('ow_download_history.retention_days', default=365) or 0)
        if retention_days <= 0:
            return
        cutoff = fields.Datetime.now() - timedelta(days=retention_days)
        self.sudo().search([('download_date', '<', cutoff)]).unlink()
