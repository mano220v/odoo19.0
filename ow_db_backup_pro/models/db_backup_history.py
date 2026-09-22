from odoo import fields, models, _
from odoo.exceptions import UserError


class DbBackupHistory(models.Model):
    _name = 'db.backup.history'
    _description = 'Database Backup History'
    _order = 'create_date desc'
    _rec_name = 'backup_filename'

    config_id = fields.Many2one('db.backup.config', string='Configuration', ondelete='cascade', index=True)
    database_name = fields.Char(string='Database')
    backup_filename = fields.Char(string='File Name')
    status = fields.Selection([
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped (Already Running)'),
        ('deleted', 'Deleted (Retention)'),
    ], default='running', string='Status', index=True)
    storage_type = fields.Selection(related='config_id.storage_type', store=True, string='Destination')
    file_location = fields.Char(string='Storage Path / ID')
    file_size = fields.Float(string='Size (bytes)')
    file_size_human = fields.Char(string='Size', compute='_compute_file_size_human')
    duration = fields.Float(string='Duration (s)')
    error_message = fields.Text(string='Error Details')
    checksum_sha256 = fields.Char(string='SHA-256 Checksum', readonly=True, index=True)
    integrity_state = fields.Selection([
        ('not_checked', 'Not Checked'),
        ('pending', 'Verification Pending'),
        ('verified', 'Verified'),
        ('failed', 'Verification Failed'),
    ], default='not_checked', string='Integrity', index=True)
    verified_at = fields.Datetime(string='Verified At')
    verification_message = fields.Text(string='Verification Details')
    deleted_at = fields.Datetime(string='Deleted At')
    retention_error = fields.Text(string='Retention Error')

    def _compute_file_size_human(self):
        for rec in self:
            size = rec.file_size or 0.0
            human = '0 B'
            for unit in ('B', 'KB', 'MB', 'GB'):
                if size < 1024.0:
                    human = '%3.1f %s' % (size, unit)
                    break
                size /= 1024.0
            else:
                human = '%3.1f TB' % size
            rec.file_size_human = human

    def action_download(self):
        self.ensure_one()
        if self.storage_type != 'local' or self.status != 'success':
            raise UserError(_('Download is only available for backups stored locally.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/db_backup_pro/download/%s' % self.id,
            'target': 'self',
        }

    def action_restore(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Restore Database'),
            'res_model': 'db.backup.restore.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_history_id': self.id, 'default_source': 'history'},
        }

    def action_verify_integrity(self):
        self.ensure_one()
        if self.status != 'success':
            raise UserError(_('Only successful backups can be verified.'))
        try:
            self.config_id._verify_history_integrity(self)
        except Exception as exc:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Integrity verification failed'),
                    'message': str(exc),
                    'type': 'danger',
                    'sticky': True,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Integrity verified'),
                'message': _('The stored file matches SHA-256 checksum %s.') % self.checksum_sha256,
                'type': 'success',
            },
        }

    def action_retry(self):
        self.ensure_one()
        if self.status not in ('failed', 'skipped'):
            raise UserError(_('Retry is available only for failed or skipped backups.'))
        history = self.config_id._run_single_backup(self.database_name or self.config_id.database_name)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Backup Result'),
            'res_model': 'db.backup.history',
            'res_id': history.id,
            'view_mode': 'form',
        }
