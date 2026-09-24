import os
import shutil
import stat
import tempfile

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBackupIntegrity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.write({
            'group_ids': [(4, cls.env.ref('ow_db_backup_pro.group_backup_manager').id)],
        })
        cls.backup_root = tempfile.mkdtemp(prefix='odoo_backup_pro_test_')
        cls.env['ir.config_parameter'].sudo().set_param(
            'ow_db_backup_pro.allowed_backup_root', cls.backup_root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.backup_root, ignore_errors=True)
        super().tearDownClass()

    def test_local_backup_checksum_and_permissions(self):
        config = self.env['db.backup.config'].create({
            'name': 'Local integrity test',
            'database_name': self.env.cr.dbname,
            'schedule_active': False,
            'storage_type': 'local',
            'local_folder': os.path.join(self.backup_root, 'daily'),
            'backup_format': 'zip',
            'verify_after_backup': True,
            'retention_policy': 'count',
            'retention_count': 2,
        })
        history = config._run_single_backup(self.env.cr.dbname)
        self.assertEqual(history.status, 'success')
        self.assertEqual(history.integrity_state, 'verified')
        self.assertEqual(len(history.checksum_sha256), 64)
        self.assertTrue(os.path.isfile(history.file_location))
        self.assertEqual(stat.S_IMODE(os.stat(history.file_location).st_mode), 0o600)

        with open(history.file_location, 'ab') as backup_file:
            backup_file.write(b'corruption')
        result = history.action_verify_integrity()
        self.assertEqual(result['params']['type'], 'danger')
        self.assertEqual(history.integrity_state, 'failed')

    def test_local_root_is_enforced(self):
        config = self.env['db.backup.config'].create({
            'name': 'Path boundary test',
            'database_name': self.env.cr.dbname,
            'schedule_active': False,
            'storage_type': 'local',
            'local_folder': '/tmp/outside-approved-backup-root',
        })
        with self.assertRaises(UserError):
            config._test_local()
