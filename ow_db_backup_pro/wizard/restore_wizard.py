import base64
import os
import tempfile

from odoo import fields, models, _
from odoo.exceptions import UserError


class DbBackupRestoreWizard(models.TransientModel):
    _name = 'db.backup.restore.wizard'
    _description = 'Restore Database From Backup'

    history_id = fields.Many2one('db.backup.history', string='Backup Record')
    source = fields.Selection([
        ('history', 'From Backup History (local storage)'),
        ('upload', 'Upload Backup File'),
    ], default='upload', required=True)
    upload_file = fields.Binary(string='Backup File')
    upload_filename = fields.Char()
    new_database_name = fields.Char(
        string='Restore Into New Database', required=True,
        help='The backup will be restored into a brand-new database with '
             'this name. It will NEVER overwrite an existing database.')

    def action_restore(self):
        self.ensure_one()
        from odoo.service import db as db_service
        from odoo.sql_db import db_connect

        if not self.new_database_name or self.new_database_name == self.env.cr.dbname:
            raise UserError(_('Choose a new, unused database name to restore into.'))

        db_conn = db_connect('postgres')
        with db_conn.cursor() as cr:
            cr.execute("SELECT datname FROM pg_database WHERE datname = %s", (self.new_database_name,))
            if cr.fetchone():
                raise UserError(_('A database with that name already exists. Choose another name.'))

        if self.source == 'history':
            if not self.history_id or self.history_id.storage_type != 'local':
                raise UserError(_(
                    'This backup is not stored locally. Download it and use '
                    '"Upload Backup File" instead.'))
            path = self.history_id.file_location
            if not path or not os.path.exists(path):
                raise UserError(_('Backup file not found on disk: %s') % path)
            with open(path, 'rb') as f:
                data = f.read()
            suffix = os.path.splitext(path)[1] or '.zip'
        else:
            if not self.upload_file:
                raise UserError(_('Please upload a backup file first.'))
            data = base64.b64decode(self.upload_file)
            suffix = os.path.splitext(self.upload_filename or '')[1] or '.zip'

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            tmp.write(data)
            tmp.close()
            # NOTE: restore_db() signature has changed slightly across Odoo
            # versions. Verify against your exact 19.0 core before relying
            # on this in production; test on a staging server first.
            db_service.restore_db(self.new_database_name, tmp.name, copy=True)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Restore complete'),
                'message': _('Database "%s" has been created.') % self.new_database_name,
                'type': 'success',
            }
        }
