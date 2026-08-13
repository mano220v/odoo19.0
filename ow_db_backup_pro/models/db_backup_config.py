import base64
import io
import json
import logging
import os
import time
import traceback
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import paramiko
except ImportError:
    paramiko = None

try:
    import boto3
except ImportError:
    boto3 = None

try:
    import dropbox
except ImportError:
    dropbox = None

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
except ImportError:
    service_account = None

try:
    import pyzipper
except ImportError:
    pyzipper = None


class DbBackupConfig(models.Model):
    _name = 'db.backup.config'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Automatic Database Backup Configuration'
    _order = 'id desc'


    name = fields.Char(string='Configuration Name', required=True, default='Backup Configuration')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    # --- What to back up ---
    database_name = fields.Char(
        string='Database Name', required=True,
        default=lambda self: self.env.cr.dbname,
        help='Database to dump. Defaults to the current database.')
    additional_databases = fields.Char(
        string='Additional Databases',
        help='Comma-separated list of extra database names on the same '
             'PostgreSQL server to back up in the same run (requires the '
             'Postgres role to have access to those databases).')
    backup_format = fields.Selection([
        ('zip', 'Full Backup (Database + Filestore)'),
        ('dump', 'SQL Dump Only'),
    ], string='Backup Format', default='zip', required=True)

    # --- Scheduling ---
    schedule_active = fields.Boolean(string='Enable Schedule', default=True)
    interval_number = fields.Integer(string='Repeat Every', default=1, required=True)
    interval_type = fields.Selection([
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
    ], string='Interval Unit', default='days', required=True)
    nextcall = fields.Datetime(string='Next Run', default=lambda self: fields.Datetime.now())
    cron_id = fields.Many2one('ir.cron', string='Scheduled Action', readonly=True, copy=False)

    # --- Storage destination ---
    storage_type = fields.Selection([
        ('local', 'Local Disk'),
        ('ftp', 'FTP'),
        ('sftp', 'SFTP'),
        ('s3', 'Amazon S3 / Compatible'),
        ('gdrive', 'Google Drive'),
        ('dropbox', 'Dropbox'),
    ], string='Storage Destination', default='local', required=True)

    # Local
    local_folder = fields.Char(string='Local Folder Path', default='/var/odoo_backups')

    # FTP / SFTP
    ftp_host = fields.Char(string='Host')
    ftp_port = fields.Integer(string='Port')
    ftp_username = fields.Char(string='Username')
    ftp_password = fields.Char(string='Password')
    ftp_directory = fields.Char(string='Remote Directory', default='/')
    sftp_private_key = fields.Text(string='Private Key (optional, PEM)')

    # S3
    s3_access_key = fields.Char(string='Access Key ID')
    s3_secret_key = fields.Char(string='Secret Access Key')
    s3_bucket = fields.Char(string='Bucket Name')
    s3_region = fields.Char(string='Region', default='us-east-1')
    s3_endpoint_url = fields.Char(string='Custom Endpoint URL',
                                   help='Leave empty for AWS. Set for MinIO / DigitalOcean Spaces / Wasabi etc.')
    s3_path_prefix = fields.Char(string='Path Prefix', default='odoo-backups/')

    # Google Drive
    gdrive_service_account_file = fields.Binary(string='Service Account JSON Key')
    gdrive_service_account_filename = fields.Char(string='Key Filename')
    gdrive_folder_id = fields.Char(string='Target Folder ID')

    # Dropbox
    dropbox_access_token = fields.Char(string='Access Token')
    dropbox_folder = fields.Char(string='Folder Path', default='/odoo-backups')

    # --- Retention ---
    retention_policy = fields.Selection([
        ('forever', 'Keep Forever'),
        ('count', 'Keep Last N Backups'),
        ('days', 'Keep for N Days'),
    ], string='Retention Policy', default='count', required=True)
    retention_count = fields.Integer(string='Number of Backups to Keep', default=7)
    retention_days = fields.Integer(string='Number of Days to Keep', default=30)

    # --- Security ---
    encrypt_backup = fields.Boolean(string='Encrypt Backup (AES-256 ZIP)')
    backup_password = fields.Char(string='Backup Password')

    # --- Notifications ---
    notify_on_success = fields.Boolean(string='Notify on Success')
    notify_on_failure = fields.Boolean(string='Notify on Failure', default=True)
    notify_user_ids = fields.Many2many('res.users', string='Notify Users')
    notify_extra_emails = fields.Char(string='Extra Email Addresses', help='Comma separated')

    # --- Stats / status ---
    history_ids = fields.One2many('db.backup.history', 'config_id', string='Backup History')
    history_count = fields.Integer(compute='_compute_history_stats')
    success_count = fields.Integer(compute='_compute_history_stats')
    failure_count = fields.Integer(compute='_compute_history_stats')
    last_backup_status = fields.Selection([
        ('success', 'Success'), ('failed', 'Failed'), ('running', 'Running'),
    ], compute='_compute_history_stats', string='Last Status')
    last_backup_date = fields.Datetime(compute='_compute_history_stats', string='Last Backup')
    total_storage_used = fields.Float(compute='_compute_history_stats', string='Storage Used (MB)')

    @api.depends('history_ids', 'history_ids.status', 'history_ids.file_size')
    def _compute_history_stats(self):
        for rec in self:
            histories = rec.history_ids
            rec.history_count = len(histories)
            rec.success_count = len(histories.filtered(lambda h: h.status == 'success'))
            rec.failure_count = len(histories.filtered(lambda h: h.status == 'failed'))
            last = histories.sorted('create_date', reverse=True)[:1]
            rec.last_backup_status = last.status if last else False
            rec.last_backup_date = last.create_date if last else False
            rec.total_storage_used = sum(
                histories.filtered(lambda h: h.status == 'success').mapped('file_size')
            ) / (1024.0 * 1024.0)

    # ------------------------------------------------------------------
    # Cron management
    # ------------------------------------------------------------------
    def _sync_cron(self):
        cron_obj = self.env['ir.cron'].sudo()
        for rec in self:
            if rec.schedule_active:
                vals = {
                    'name': _('Auto Backup: %s') % rec.name,
                    'model_id': self.env['ir.model']._get_id('db.backup.config'),
                    'state': 'code',
                    'code': "env['db.backup.config'].browse(%d)._run_backup()" % rec.id,
                    'interval_number': rec.interval_number,
                    'interval_type': rec.interval_type,
                    'numbercall': -1,
                    'active': True,
                    'nextcall': rec.nextcall or fields.Datetime.now(),
                }
                if rec.cron_id:
                    rec.cron_id.write(vals)
                else:
                    rec.cron_id = cron_obj.create(vals)
            elif rec.cron_id:
                rec.cron_id.active = False

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_cron()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ('schedule_active', 'interval_number', 'interval_type', 'nextcall', 'name')):
            self._sync_cron()
        return res

    def unlink(self):
        crons = self.mapped('cron_id')
        res = super().unlink()
        crons.unlink()
        return res

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_backup_now(self):
        for rec in self:
            rec._run_backup()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Backup finished'),
                'message': _('Check the Backup History for results.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_test_connection(self):
        self.ensure_one()
        try:
            ok, message = self._test_storage_connection()
        except Exception as e:  # noqa
            ok, message = False, str(e)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connection OK') if ok else _('Connection Failed'),
                'message': message,
                'type': 'success' if ok else 'danger',
                'sticky': not ok,
            }
        }

    def action_view_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Backup History'),
            'res_model': 'db.backup.history',
            'view_mode': 'list,form,graph,pivot',
            'domain': [('config_id', '=', self.id)],
        }

    # ------------------------------------------------------------------
    # Core backup logic
    # ------------------------------------------------------------------
    def _run_backup(self):
        for rec in self:
            db_names = [rec.database_name] if rec.database_name else [self.env.cr.dbname]
            if rec.additional_databases:
                db_names += [d.strip() for d in rec.additional_databases.split(',') if d.strip()]
            for db_name in db_names:
                rec._run_single_backup(db_name)

    def _run_single_backup(self, db_name):
        self.ensure_one()
        history = self.env['db.backup.history'].sudo().create({
            'config_id': self.id,
            'database_name': db_name,
            'status': 'running',
        })
        start = time.time()
        try:
            data, filename = self._dump_database(db_name)
            if self.encrypt_backup:
                data, filename = self._encrypt_backup_data(data, filename)
            size = len(data)
            location = self._upload_to_storage(data, filename)
            duration = time.time() - start
            history.write({
                'status': 'success',
                'duration': duration,
                'file_size': size,
                'file_location': location,
                'backup_filename': filename,
            })
            self._cleanup_retention()
            if self.notify_on_success:
                self._send_notification(history, success=True)
        except Exception as e:  # noqa
            duration = time.time() - start
            _logger.exception('Database backup failed for %s', db_name)
            history.write({
                'status': 'failed',
                'duration': duration,
                'error_message': '%s\n\n%s' % (str(e), traceback.format_exc()),
            })
            if self.notify_on_failure:
                self._send_notification(history, success=False)
        return history

    def _dump_database(self, db_name):
        from odoo.service import db as db_service
        stream = io.BytesIO()
        db_service.dump_db(db_name, stream, backup_format=self.backup_format)
        stream.seek(0)
        data = stream.read()
        ext = 'zip' if self.backup_format == 'zip' else 'dump'
        timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = '%s_%s.%s' % (db_name, timestamp, ext)
        return data, filename

    def _encrypt_backup_data(self, data, filename):
        if not pyzipper:
            raise UserError(_(
                'Encryption requires the "pyzipper" Python library. '
                'Install it on the server with: pip install pyzipper'))
        if not self.backup_password:
            raise UserError(_('Set a backup password to enable encryption.'))
        out = io.BytesIO()
        with pyzipper.AESZipFile(out, 'w', compression=pyzipper.ZIP_LZMA,
                                  encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(self.backup_password.encode())
            zf.writestr(filename, data)
        return out.getvalue(), filename + '.enc.zip'

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------
    def _cleanup_retention(self):
        self.ensure_one()
        if self.retention_policy == 'forever':
            return
        histories = self.env['db.backup.history'].sudo().search([
            ('config_id', '=', self.id),
            ('status', '=', 'success'),
        ], order='create_date desc')
        to_delete = self.env['db.backup.history']
        if self.retention_policy == 'count':
            to_delete = histories[self.retention_count:]
        elif self.retention_policy == 'days':
            cutoff = fields.Datetime.now() - timedelta(days=self.retention_days)
            to_delete = histories.filtered(lambda h: h.create_date < cutoff)
        for h in to_delete:
            try:
                self._delete_from_storage(h)
            except Exception:  # noqa
                _logger.exception('Could not delete old backup %s from storage', h.backup_filename)
            h.write({'status': 'deleted'})

    # ------------------------------------------------------------------
    # Storage dispatch
    # ------------------------------------------------------------------
    def _upload_to_storage(self, data, filename):
        self.ensure_one()
        method = getattr(self, '_upload_%s' % self.storage_type, None)
        if not method:
            raise UserError(_('Unsupported storage type: %s') % self.storage_type)
        return method(data, filename)

    def _delete_from_storage(self, history):
        self.ensure_one()
        method = getattr(self, '_delete_%s' % self.storage_type, None)
        if method and history.file_location:
            method(history)

    def _test_storage_connection(self):
        self.ensure_one()
        method = getattr(self, '_test_%s' % self.storage_type, None)
        if not method:
            return False, _('Unsupported storage type')
        return method()

    # ---- Local ----
    def _upload_local(self, data, filename):
        folder = self.local_folder or '/var/odoo_backups'
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def _delete_local(self, history):
        if history.file_location and os.path.exists(history.file_location):
            os.remove(history.file_location)

    def _test_local(self):
        folder = self.local_folder or '/var/odoo_backups'
        try:
            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            test_file = os.path.join(folder, '.write_test')
            with open(test_file, 'w') as f:
                f.write('ok')
            os.remove(test_file)
            return True, _('Folder is writable: %s') % folder
        except Exception as e:  # noqa
            return False, str(e)

    # ---- FTP ----
    def _get_ftp_connection(self):
        import ftplib
        ftp = ftplib.FTP()
        ftp.connect(self.ftp_host, self.ftp_port or 21, timeout=30)
        ftp.login(self.ftp_username, self.ftp_password)
        if self.ftp_directory:
            try:
                ftp.cwd(self.ftp_directory)
            except ftplib.error_perm:
                self._ftp_mkdirs(ftp, self.ftp_directory)
                ftp.cwd(self.ftp_directory)
        return ftp

    def _ftp_mkdirs(self, ftp, path):
        parts = [p for p in path.split('/') if p]
        cur = ''
        for p in parts:
            cur += '/' + p
            try:
                ftp.mkd(cur)
            except Exception:  # noqa
                pass

    def _upload_ftp(self, data, filename):
        ftp = self._get_ftp_connection()
        try:
            ftp.storbinary('STOR %s' % filename, io.BytesIO(data))
        finally:
            ftp.quit()
        return '%s/%s' % ((self.ftp_directory or '').rstrip('/'), filename)

    def _delete_ftp(self, history):
        ftp = self._get_ftp_connection()
        try:
            ftp.delete(os.path.basename(history.file_location))
        finally:
            ftp.quit()

    def _test_ftp(self):
        try:
            ftp = self._get_ftp_connection()
            ftp.quit()
            return True, _('FTP connection successful')
        except Exception as e:  # noqa
            return False, str(e)

    # ---- SFTP ----
    def _get_sftp_connection(self):
        if not paramiko:
            raise UserError(_('SFTP requires the "paramiko" Python library. '
                               'Install it on the server with: pip install paramiko'))
        transport = paramiko.Transport((self.ftp_host, self.ftp_port or 22))
        if self.sftp_private_key:
            key = paramiko.RSAKey.from_private_key(io.StringIO(self.sftp_private_key))
            transport.connect(username=self.ftp_username, pkey=key)
        else:
            transport.connect(username=self.ftp_username, password=self.ftp_password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        return sftp, transport

    def _sftp_mkdirs(self, sftp, path):
        parts = [p for p in path.split('/') if p]
        cur = ''
        for p in parts:
            cur += '/' + p
            try:
                sftp.mkdir(cur)
            except IOError:
                pass

    def _upload_sftp(self, data, filename):
        sftp, transport = self._get_sftp_connection()
        try:
            remote_dir = self.ftp_directory or '/'
            try:
                sftp.chdir(remote_dir)
            except IOError:
                self._sftp_mkdirs(sftp, remote_dir)
                sftp.chdir(remote_dir)
            with sftp.open(filename, 'wb') as f:
                f.write(data)
            return '%s/%s' % (remote_dir.rstrip('/'), filename)
        finally:
            sftp.close()
            transport.close()

    def _delete_sftp(self, history):
        sftp, transport = self._get_sftp_connection()
        try:
            sftp.remove(history.file_location)
        finally:
            sftp.close()
            transport.close()

    def _test_sftp(self):
        try:
            sftp, transport = self._get_sftp_connection()
            sftp.close()
            transport.close()
            return True, _('SFTP connection successful')
        except Exception as e:  # noqa
            return False, str(e)

    # ---- S3 ----
    def _get_s3_client(self):
        if not boto3:
            raise UserError(_('Amazon S3 requires the "boto3" Python library. '
                               'Install it on the server with: pip install boto3'))
        return boto3.client(
            's3',
            aws_access_key_id=self.s3_access_key,
            aws_secret_access_key=self.s3_secret_key,
            region_name=self.s3_region or 'us-east-1',
            endpoint_url=self.s3_endpoint_url or None,
        )

    def _upload_s3(self, data, filename):
        client = self._get_s3_client()
        key = '%s%s' % (self.s3_path_prefix or '', filename)
        client.put_object(Bucket=self.s3_bucket, Key=key, Body=data)
        return key

    def _delete_s3(self, history):
        client = self._get_s3_client()
        client.delete_object(Bucket=self.s3_bucket, Key=history.file_location)

    def _test_s3(self):
        try:
            client = self._get_s3_client()
            client.head_bucket(Bucket=self.s3_bucket)
            return True, _('S3 bucket reachable: %s') % self.s3_bucket
        except Exception as e:  # noqa
            return False, str(e)

    # ---- Google Drive ----
    def _get_gdrive_service(self):
        if not service_account:
            raise UserError(_('Google Drive requires "google-api-python-client" and '
                               '"google-auth". Install with: '
                               'pip install google-api-python-client google-auth'))
        if not self.gdrive_service_account_file:
            raise UserError(_('Upload a Service Account JSON key first.'))
        key_data = base64.b64decode(self.gdrive_service_account_file)
        info = json.loads(key_data)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/drive'])
        return build('drive', 'v3', credentials=creds)

    def _upload_gdrive(self, data, filename):
        service = self._get_gdrive_service()
        file_metadata = {'name': filename}
        if self.gdrive_folder_id:
            file_metadata['parents'] = [self.gdrive_folder_id]
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype='application/octet-stream', resumable=True)
        uploaded = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return uploaded.get('id')

    def _delete_gdrive(self, history):
        service = self._get_gdrive_service()
        service.files().delete(fileId=history.file_location).execute()

    def _test_gdrive(self):
        try:
            service = self._get_gdrive_service()
            service.files().list(pageSize=1).execute()
            return True, _('Google Drive connection successful')
        except Exception as e:  # noqa
            return False, str(e)

    # ---- Dropbox ----
    def _get_dropbox_client(self):
        if not dropbox:
            raise UserError(_('Dropbox requires the "dropbox" Python library. '
                               'Install it on the server with: pip install dropbox'))
        if not self.dropbox_access_token:
            raise UserError(_('Set a Dropbox Access Token first.'))
        return dropbox.Dropbox(self.dropbox_access_token)

    def _upload_dropbox(self, data, filename):
        dbx = self._get_dropbox_client()
        path = '%s/%s' % ((self.dropbox_folder or '/odoo-backups').rstrip('/'), filename)
        dbx.files_upload(data, path, mode=dropbox.files.WriteMode('overwrite'))
        return path

    def _delete_dropbox(self, history):
        dbx = self._get_dropbox_client()
        dbx.files_delete_v2(history.file_location)

    def _test_dropbox(self):
        try:
            dbx = self._get_dropbox_client()
            dbx.users_get_current_account()
            return True, _('Dropbox connection successful')
        except Exception as e:  # noqa
            return False, str(e)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def _send_notification(self, history, success=True):
        self.ensure_one()
        emails = []
        for user in self.notify_user_ids:
            if user.email:
                emails.append(user.email)
        if self.notify_extra_emails:
            emails += [e.strip() for e in self.notify_extra_emails.split(',') if e.strip()]
        if not emails:
            return
        template = self.env.ref(
            'ow_db_backup_pro.mail_template_backup_success' if success
            else 'ow_db_backup_pro.mail_template_backup_failure',
            raise_if_not_found=False)
        if not template:
            return
        for email in emails:
            template.sudo().send_mail(
                history.id, force_send=True,
                email_values={'email_to': email})
