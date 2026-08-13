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
        ('deleted', 'Deleted (Retention)'),
    ], default='running', string='Status', index=True)
    storage_type = fields.Selection(related='config_id.storage_type', store=True, string='Destination')
    file_location = fields.Char(string='Storage Path / ID')
    file_size = fields.Float(string='Size (bytes)')
    file_size_human = fields.Char(string='Size', compute='_compute_file_size_human')
    duration = fields.Float(string='Duration (s)')
    error_message = fields.Text(string='Error Details')

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
