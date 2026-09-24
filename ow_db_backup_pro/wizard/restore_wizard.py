import base64
import io
import os
import tempfile
import re

from odoo import fields, models, _
from odoo.exceptions import UserError

try:
    import pyzipper
except ImportError:
    pyzipper = None


class DbBackupRestoreWizard(models.TransientModel):
    _name = 'db.backup.restore.wizard'
    _description = 'Restore Database From Backup'

    history_id = fields.Many2one('db.backup.history', string='Backup Record')
    source = fields.Selection([
        ('history', 'From Backup History'),
        ('upload', 'Upload Backup File'),
    ], default='upload', required=True)
    upload_file = fields.Binary(string='Backup File')
    upload_filename = fields.Char()
    new_database_name = fields.Char(
        string='Restore Into New Database', required=True,
        help='The backup will be restored into a brand-new database with '
             'this name. It will NEVER overwrite an existing database.')
    encryption_password = fields.Char(
        string='Encryption Password',
        help='Required only for AES-encrypted .enc.zip backups.')

    def action_restore(self):
        self.ensure_one()
        from odoo.service import db as db_service
        from odoo.sql_db import db_connect

        if not self.new_database_name or self.new_database_name == self.env.cr.dbname:
            raise UserError(_('Choose a new, unused database name to restore into.'))
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', self.new_database_name):
            raise UserError(_('Database name may contain only letters, numbers, dots, underscores and hyphens.'))

        db_conn = db_connect('postgres')
        with db_conn.cursor() as cr:
            cr.execute("SELECT datname FROM pg_database WHERE datname = %s", (self.new_database_name,))
            if cr.fetchone():
                raise UserError(_('A database with that name already exists. Choose another name.'))

        if self.source == 'history':
            if not self.history_id or self.history_id.status != 'success':
                raise UserError(_('Choose a successful backup history record.'))
            data = self.history_id.config_id._download_from_storage(self.history_id)
            filename = self.history_id.backup_filename or ''
            suffix = os.path.splitext(filename)[1] or '.zip'
        else:
            if not self.upload_file:
                raise UserError(_('Please upload a backup file first.'))
            data = base64.b64decode(self.upload_file)
            filename = self.upload_filename or ''
            suffix = os.path.splitext(filename)[1] or '.zip'

        if filename.endswith('.enc.zip'):
            if not pyzipper:
                raise UserError(_('Encrypted restore requires the "pyzipper" Python library.'))
            if not self.encryption_password:
                raise UserError(_('Enter the encryption password for this backup.'))
            try:
                with pyzipper.AESZipFile(io.BytesIO(data), 'r') as archive:
                    archive.setpassword(self.encryption_password.encode())
                    members = archive.namelist()
                    if len(members) != 1:
                        raise UserError(_('Encrypted backup archive has an unexpected structure.'))
                    inner_name = members[0]
                    data = archive.read(inner_name)
                    suffix = os.path.splitext(inner_name)[1] or '.zip'
            except RuntimeError as exc:
                raise UserError(_('Unable to decrypt backup. Check the encryption password.')) from exc

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
