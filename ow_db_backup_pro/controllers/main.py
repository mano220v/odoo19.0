import os

from odoo import http
from odoo.http import request


class DbBackupProController(http.Controller):

    @http.route('/db_backup_pro/download/<int:history_id>', type='http', auth='user')
    def download_backup(self, history_id, **kw):
        history = request.env['db.backup.history'].sudo().browse(history_id)
        if not history.exists():
            return request.not_found()
        if not request.env.user.has_group('ow_db_backup_pro.group_backup_manager'):
            return request.not_found()
        if history.storage_type != 'local' or history.status != 'success':
            return request.not_found()
        path = history.file_location
        if not path or not os.path.exists(path):
            return request.not_found()
        with open(path, 'rb') as f:
            data = f.read()
        filename = history.backup_filename or os.path.basename(path)
        headers = [
            ('Content-Type', 'application/octet-stream'),
            ('Content-Disposition', 'attachment; filename="%s"' % filename),
            ('Content-Length', len(data)),
        ]
        return request.make_response(data, headers=headers)
