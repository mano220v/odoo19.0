import base64
import io

from odoo import fields, models


class DbBackupNowWizard(models.TransientModel):
    _name = 'db.backup.now.wizard'
    _description = 'Instant Database Backup'

    database_name = fields.Char(default=lambda self: self.env.cr.dbname, required=True)
    backup_format = fields.Selection([
        ('zip', 'Full Backup (Database + Filestore)'),
        ('dump', 'SQL Dump Only'),
    ], default='zip', required=True)
    backup_file = fields.Binary(string='Backup File', readonly=True)
    backup_filename = fields.Char(readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')

    def action_generate(self):
        self.ensure_one()
        from odoo.service import db as db_service
        stream = io.BytesIO()
        db_service.dump_db(self.database_name, stream, backup_format=self.backup_format)
        stream.seek(0)
        data = stream.read()
        ext = 'zip' if self.backup_format == 'zip' else 'dump'
        timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = '%s_%s.%s' % (self.database_name, timestamp, ext)
        self.write({
            'backup_file': base64.b64encode(data),
            'backup_filename': filename,
            'state': 'done',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'db.backup.now.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
