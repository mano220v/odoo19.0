import base64
import hashlib
import io
import json
import logging
import os
import re
import time
import traceback
from datetime import timedelta
from urllib.parse import quote, urljoin, urlparse

import requests

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
        ('webdav', 'WebDAV / Nextcloud'),
    ], string='Storage Destination', default='local', required=True)

    # Local
    local_folder = fields.Char(string='Local Folder Path', default='/var/odoo_backups')

    # FTP / SFTP
    ftp_host = fields.Char(string='Host')
    ftp_port = fields.Integer(string='Port')
    ftp_username = fields.Char(string='Username')
    ftp_password = fields.Char(string='Password')
    ftp_directory = fields.Char(string='Remote Directory', default='/')
    ftp_tls = fields.Boolean(string='Use Explicit TLS (FTPS)')
    sftp_private_key = fields.Text(string='Private Key (optional, PEM)')

    # S3
    s3_access_key = fields.Char(string='Access Key ID')
    s3_secret_key = fields.Char(string='Secret Access Key')
    s3_bucket = fields.Char(string='Bucket Name')
    s3_region = fields.Char(string='Region', default='us-east-1')
    s3_endpoint_url = fields.Char(string='Custom Endpoint URL',
                                   help='Leave empty for AWS. Set for MinIO / DigitalOcean Spaces / Wasabi etc.')
    s3_path_prefix = fields.Char(string='Path Prefix', default='odoo-backups/')
    s3_server_side_encryption = fields.Selection([
        ('none', 'None'),
        ('AES256', 'Amazon S3 managed key (AES-256)'),
        ('aws:kms', 'AWS KMS key'),
    ], string='Server-side Encryption', default='none')
    s3_kms_key_id = fields.Char(string='KMS Key ID')
    s3_storage_class = fields.Selection([
        ('STANDARD', 'Standard'),
        ('STANDARD_IA', 'Standard - Infrequent Access'),
        ('ONEZONE_IA', 'One Zone - Infrequent Access'),
        ('INTELLIGENT_TIERING', 'Intelligent Tiering'),
        ('GLACIER_IR', 'Glacier Instant Retrieval'),
    ], default='STANDARD', string='Storage Class')

    # Google Drive
    gdrive_service_account_file = fields.Binary(string='Service Account JSON Key')
    gdrive_service_account_filename = fields.Char(string='Key Filename')
    gdrive_folder_id = fields.Char(string='Target Folder ID')

    # Dropbox
    dropbox_access_token = fields.Char(string='Access Token')
    dropbox_folder = fields.Char(string='Folder Path', default='/odoo-backups')

    # WebDAV / Nextcloud
    webdav_url = fields.Char(string='WebDAV Base URL')
    webdav_username = fields.Char(string='WebDAV Username')
    webdav_password = fields.Char(string='WebDAV Password')
    webdav_folder = fields.Char(string='WebDAV Folder', default='odoo-backups')
    webdav_verify_ssl = fields.Boolean(string='Verify TLS Certificate', default=True)

    # --- Retention ---
    retention_policy = fields.Selection([
        ('forever', 'Keep Forever'),
        ('count', 'Keep Last N Backups'),
        ('days', 'Keep for N Days'),
    ], string='Retention Policy', default='count', required=True)
    retention_count = fields.Integer(string='Number of Backups to Keep', default=7)
    retention_days = fields.Integer(string='Number of Days to Keep', default=30)
    verify_after_backup = fields.Boolean(
        string='Verify After Upload', default=True,
        help='Downloads the stored object and compares its SHA-256 checksum. This doubles transfer usage for remote destinations.')

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
    verified_count = fields.Integer(compute='_compute_history_stats')
    health_state = fields.Selection([
        ('empty', 'No Backup'), ('healthy', 'Healthy'),
        ('warning', 'Warning'), ('critical', 'Critical'),
    ], compute='_compute_health', string='Backup Health')
    health_message = fields.Char(compute='_compute_health')
    max_backup_age_hours = fields.Integer(
        string='Maximum Backup Age (hours)', default=26,
        help='Health becomes critical when the last successful backup is older than this value.')

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
            rec.verified_count = len(histories.filtered(lambda h: h.status == 'success' and h.integrity_state == 'verified'))

    @api.depends('history_ids.status', 'history_ids.create_date', 'history_ids.integrity_state', 'max_backup_age_hours')
    def _compute_health(self):
        now = fields.Datetime.now()
        for rec in self:
            latest = rec.history_ids.filtered(lambda item: item.status in ('success', 'failed')).sorted('create_date', reverse=True)[:1]
            latest_success = rec.history_ids.filtered(lambda item: item.status == 'success').sorted('create_date', reverse=True)[:1]
            if not latest:
                rec.health_state = 'empty'
                rec.health_message = _('No backup has run yet.')
            elif latest.status == 'failed':
                rec.health_state = 'critical'
                rec.health_message = _('The most recent backup failed.')
            elif latest_success and rec.max_backup_age_hours and latest_success.create_date < now - timedelta(hours=rec.max_backup_age_hours):
                rec.health_state = 'critical'
                rec.health_message = _('The last successful backup is older than %s hours.') % rec.max_backup_age_hours
            elif latest.integrity_state == 'failed':
                rec.health_state = 'critical'
                rec.health_message = _('The latest backup failed integrity verification.')
            elif latest.integrity_state != 'verified':
                rec.health_state = 'warning'
                rec.health_message = _('The latest backup has not been verified.')
            else:
                rec.health_state = 'healthy'
                rec.health_message = _('Latest backup is successful and verified.')

    @api.constrains('interval_number', 'retention_count', 'retention_days', 'max_backup_age_hours')
    def _check_positive_values(self):
        for rec in self:
            if rec.interval_number <= 0:
                raise UserError(_('Schedule interval must be greater than zero.'))
            if rec.retention_policy == 'count' and rec.retention_count <= 0:
                raise UserError(_('Retention count must be greater than zero.'))
            if rec.retention_policy == 'days' and rec.retention_days <= 0:
                raise UserError(_('Retention days must be greater than zero.'))
            if rec.max_backup_age_hours < 0:
                raise UserError(_('Maximum backup age cannot be negative.'))

    @api.constrains('database_name', 'additional_databases')
    def _check_database_names(self):
        pattern = re.compile(r'^[A-Za-z0-9_.-]+$')
        for rec in self:
            names = [rec.database_name] + [item.strip() for item in (rec.additional_databases or '').split(',') if item.strip()]
            if any(name and not pattern.fullmatch(name) for name in names):
                raise UserError(_('Database names may contain only letters, numbers, dots, underscores and hyphens.'))

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
        lock_key = 'ow_db_backup_pro:%s:%s' % (self.id, db_name)
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(hashtext(%s))', (lock_key,))
        if not self.env.cr.fetchone()[0]:
            return self.env['db.backup.history'].sudo().create({
                'config_id': self.id,
                'database_name': db_name,
                'status': 'skipped',
                'error_message': _('Another backup for this configuration and database is already running.'),
            })
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
            checksum = hashlib.sha256(data).hexdigest()
            location = self._upload_to_storage(data, filename)
            history.write({
                'file_size': size,
                'file_location': location,
                'backup_filename': filename,
                'checksum_sha256': checksum,
                'integrity_state': 'pending' if self.verify_after_backup else 'not_checked',
            })
            if self.verify_after_backup:
                self._verify_history_integrity(history)
            duration = time.time() - start
            history.write({
                'status': 'success',
                'duration': duration,
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
                h.write({'status': 'deleted', 'deleted_at': fields.Datetime.now(), 'retention_error': False})
            except Exception as exc:  # noqa
                _logger.exception('Could not delete old backup %s from storage', h.backup_filename)
                h.write({'retention_error': str(exc)})

    # ------------------------------------------------------------------
    # Storage dispatch
    # ------------------------------------------------------------------
    def _upload_to_storage(self, data, filename):
        self.ensure_one()
        method = getattr(self, '_upload_%s' % self.storage_type, None)
        if not method:
            raise UserError(_('Unsupported storage type: %s') % self.storage_type)
        return method(data, filename)

    def _download_from_storage(self, history):
        self.ensure_one()
        method = getattr(self, '_download_%s' % self.storage_type, None)
        if not method:
            raise UserError(_('Integrity verification is not supported for destination: %s') % self.storage_type)
        return method(history)

    def _verify_history_integrity(self, history):
        self.ensure_one()
        try:
            stored_data = self._download_from_storage(history)
            actual = hashlib.sha256(stored_data).hexdigest()
            if actual != history.checksum_sha256:
                history.write({
                    'integrity_state': 'failed',
                    'verified_at': fields.Datetime.now(),
                    'verification_message': _('Checksum mismatch. Expected %s but received %s.') % (history.checksum_sha256, actual),
                })
                raise UserError(_('Backup upload verification failed: SHA-256 checksum mismatch.'))
            history.write({
                'integrity_state': 'verified',
                'verified_at': fields.Datetime.now(),
                'verification_message': _('Stored backup matches its SHA-256 checksum.'),
            })
            return True
        except Exception as exc:
            if history.integrity_state != 'failed':
                history.write({
                    'integrity_state': 'failed',
                    'verified_at': fields.Datetime.now(),
                    'verification_message': str(exc),
                })
            raise

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
    def _safe_local_folder(self):
        self.ensure_one()
        folder = os.path.realpath(os.path.expanduser(self.local_folder or '/var/odoo_backups'))
        allowed_root = self.env['ir.config_parameter'].sudo().get_param('ow_db_backup_pro.allowed_backup_root')
        if allowed_root:
            root = os.path.realpath(os.path.expanduser(allowed_root))
            if folder != root and not folder.startswith(root + os.sep):
                raise UserError(_('Local backup folder must be inside the configured allowed backup root: %s') % root)
        return folder

    def _upload_local(self, data, filename):
        folder = self._safe_local_folder()
        if not os.path.exists(folder):
            os.makedirs(folder, mode=0o700, exist_ok=True)
        path = os.path.join(folder, filename)
        with open(path, 'wb') as f:
            f.write(data)
        os.chmod(path, 0o600)
        return path

    def _download_local(self, history):
        path = os.path.realpath(history.file_location or '')
        folder = self._safe_local_folder()
        if path != folder and not path.startswith(folder + os.sep):
            raise UserError(_('Stored backup path is outside the configured local backup folder.'))
        with open(path, 'rb') as backup_file:
            return backup_file.read()

    def _delete_local(self, history):
        path = os.path.realpath(history.file_location or '')
        folder = self._safe_local_folder()
        if path != folder and not path.startswith(folder + os.sep):
            raise UserError(_('Refusing to delete a file outside the configured local backup folder.'))
        if path and os.path.exists(path):
            os.remove(path)

    def _test_local(self):
        folder = self._safe_local_folder()
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
        ftp = ftplib.FTP_TLS() if self.ftp_tls else ftplib.FTP()
        ftp.connect(self.ftp_host, self.ftp_port or 21, timeout=30)
        ftp.login(self.ftp_username, self.ftp_password)
        if self.ftp_tls:
            ftp.prot_p()
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

    def _download_ftp(self, history):
        ftp = self._get_ftp_connection()
        output = io.BytesIO()
        try:
            ftp.retrbinary('RETR %s' % os.path.basename(history.file_location), output.write)
            return output.getvalue()
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

    def _download_sftp(self, history):
        sftp, transport = self._get_sftp_connection()
        try:
            with sftp.open(history.file_location, 'rb') as remote_file:
                return remote_file.read()
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
        values = {
            'Bucket': self.s3_bucket,
            'Key': key,
            'Body': data,
            'StorageClass': self.s3_storage_class or 'STANDARD',
            'Metadata': {'sha256': hashlib.sha256(data).hexdigest()},
        }
        if self.s3_server_side_encryption != 'none':
            values['ServerSideEncryption'] = self.s3_server_side_encryption
            if self.s3_server_side_encryption == 'aws:kms' and self.s3_kms_key_id:
                values['SSEKMSKeyId'] = self.s3_kms_key_id
        client.put_object(**values)
        return key

    def _delete_s3(self, history):
        client = self._get_s3_client()
        client.delete_object(Bucket=self.s3_bucket, Key=history.file_location)

    def _download_s3(self, history):
        response = self._get_s3_client().get_object(Bucket=self.s3_bucket, Key=history.file_location)
        return response['Body'].read()

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

    def _download_gdrive(self, history):
        request = self._get_gdrive_service().files().get_media(fileId=history.file_location)
        output = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return output.getvalue()

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

    def _download_dropbox(self, history):
        _, response = self._get_dropbox_client().files_download(history.file_location)
        return response.content

    def _test_dropbox(self):
        try:
            dbx = self._get_dropbox_client()
            dbx.users_get_current_account()
            return True, _('Dropbox connection successful')
        except Exception as e:  # noqa
            return False, str(e)

    # ---- WebDAV / Nextcloud ----
    def _webdav_target_url(self, filename=None):
        self.ensure_one()
        if not self.webdav_url:
            raise UserError(_('Set the WebDAV base URL first.'))
        parsed = urlparse(self.webdav_url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise UserError(_('WebDAV URL must be a valid HTTP or HTTPS URL.'))
        base = self.webdav_url.rstrip('/') + '/'
        segments = [quote(part, safe='') for part in (self.webdav_folder or '').split('/') if part]
        if filename:
            segments.append(quote(filename, safe=''))
        return urljoin(base, '/'.join(segments))

    def _webdav_request(self, method, url, **kwargs):
        auth = (self.webdav_username or '', self.webdav_password or '')
        try:
            response = requests.request(
                method, url, auth=auth, verify=self.webdav_verify_ssl,
                timeout=120, allow_redirects=True, **kwargs)
        except requests.RequestException as exc:
            raise UserError(_('WebDAV request failed: %s') % exc) from exc
        if response.status_code >= 400:
            raise UserError(_('WebDAV returned HTTP %s: %s') % (response.status_code, response.text[:500]))
        return response

    def _ensure_webdav_folder(self):
        current = self.webdav_url.rstrip('/') + '/'
        for part in [item for item in (self.webdav_folder or '').split('/') if item]:
            current = urljoin(current, quote(part, safe='') + '/')
            response = requests.request(
                'MKCOL', current,
                auth=(self.webdav_username or '', self.webdav_password or ''),
                verify=self.webdav_verify_ssl, timeout=60,
            )
            if response.status_code not in (201, 301, 302, 405):
                raise UserError(_('Could not create WebDAV folder (HTTP %s).') % response.status_code)

    def _upload_webdav(self, data, filename):
        self._ensure_webdav_folder()
        self._webdav_request('PUT', self._webdav_target_url(filename), data=data)
        return filename

    def _download_webdav(self, history):
        return self._webdav_request('GET', self._webdav_target_url(history.backup_filename)).content

    def _delete_webdav(self, history):
        self._webdav_request('DELETE', self._webdav_target_url(history.backup_filename))

    def _test_webdav(self):
        try:
            self._webdav_request('PROPFIND', self.webdav_url.rstrip('/') + '/', headers={'Depth': '0'})
            return True, _('WebDAV connection successful')
        except Exception as exc:  # noqa
            return False, str(exc)

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
