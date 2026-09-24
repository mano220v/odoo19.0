import base64
import io
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CONTENT_CATEGORIES = ('image', 'video', 'document', 'audio', 'other')

DOC_MIME_PREFIXES = (
    'application/pdf',
    'application/msword',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats',
    'application/vnd.oasis.opendocument',
    'text/plain',
    'text/csv',
)

AUTO_CLEAN_PARAM = 'ow_cache_manager_pro.auto_clean_enabled'


def _categorize(mimetype):
    if not mimetype:
        return 'other'
    m = mimetype.lower()
    if m.startswith('image/'):
        return 'image'
    if m.startswith('video/'):
        return 'video'
    if m.startswith('audio/'):
        return 'audio'
    if any(m.startswith(p) for p in DOC_MIME_PREFIXES):
        return 'document'
    return 'other'


def _mb(num_bytes):
    return round((num_bytes or 0) / (1024 * 1024), 2)


class OwCacheManagerPro(models.TransientModel):
    _name = 'ow.cache.manager.pro'
    _description = 'Odoo Cache & Storage Manager'

    # ---------------------------------------------------------------
    # Domains / helpers
    # ---------------------------------------------------------------
    @api.model
    def _asset_cache_domain(self):
        """Regenerable web asset bundles. Odoo rebuilds these automatically
        on next request, so deleting them is always safe."""
        return [
            ('res_model', '=', 'ir.ui.view'),
            ('url', 'like', '/web/assets/%'),
        ]

    @api.model
    def _find_orphaned_attachments(self):
        """Attachments whose linked record no longer exists in the DB.
        These are genuine junk (e.g. leftover binary-field data after a
        record was deleted outside normal ORM flow, or module changes)."""
        self.env.cr.execute("""
            SELECT id, res_model, res_id
            FROM ir_attachment
            WHERE res_model IS NOT NULL
              AND res_id IS NOT NULL
              AND res_id != 0
              AND res_model != 'ir.ui.view'
        """)
        by_model = {}
        for att_id, res_model, res_id in self.env.cr.fetchall():
            by_model.setdefault(res_model, []).append((att_id, res_id))

        orphaned_ids = []
        for model_name, entries in by_model.items():
            if model_name not in self.env:
                continue
            try:
                Model = self.env[model_name].sudo()
                if getattr(Model, '_transient', False):
                    continue  # wizards get vacuumed on their own, ignore
                res_ids = [e[1] for e in entries]
                existing = set(Model.browse(res_ids).exists().ids)
            except Exception:
                _logger.warning(
                    "Cache Manager: skipped model %s while scanning for orphans",
                    model_name, exc_info=True,
                )
                continue
            orphaned_ids += [att_id for att_id, res_id in entries if res_id not in existing]

        return self.env['ir.attachment'].sudo().browse(orphaned_ids)

    @api.model
    def _log(self, action_type, freed_mb, cleared_count):
        self.env['ow.storage.log'].sudo().create({
            'action_type': action_type,
            'freed_mb': freed_mb,
            'cleared_count': cleared_count,
        })

    # ---------------------------------------------------------------
    # Generate (scan)
    # ---------------------------------------------------------------
    @api.model
    def action_generate_report(self):
        totals = {c: 0 for c in CONTENT_CATEGORIES}
        total_bytes = 0

        self.env.cr.execute("SELECT mimetype, COALESCE(file_size, 0) FROM ir_attachment")
        for mimetype, size in self.env.cr.fetchall():
            totals[_categorize(mimetype)] += size
            total_bytes += size

        asset_atts = self.env['ir.attachment'].sudo().search(self._asset_cache_domain())
        asset_bytes = sum(asset_atts.mapped('file_size'))

        orphaned = self._find_orphaned_attachments()
        orphaned_bytes = sum(orphaned.mapped('file_size'))

        return {
            'total_mb': _mb(total_bytes),
            'asset_cache_mb': _mb(asset_bytes),
            'asset_count': len(asset_atts),
            'orphaned_mb': _mb(orphaned_bytes),
            'orphaned_count': len(orphaned),
            'image_mb': _mb(totals['image']),
            'video_mb': _mb(totals['video']),
            'document_mb': _mb(totals['document']),
            'audio_mb': _mb(totals['audio']),
            'other_mb': _mb(totals['other']),
        }

    @api.model
    def action_top_models(self, limit=15):
        """Which models/apps are eating the most filestore space."""
        self.env.cr.execute("""
            SELECT COALESCE(res_model, 'Standalone / Not Linked') AS model,
                   COUNT(*), SUM(COALESCE(file_size, 0))
            FROM ir_attachment
            GROUP BY res_model
            ORDER BY SUM(COALESCE(file_size, 0)) DESC
            LIMIT %s
        """, (limit,))
        rows = self.env.cr.fetchall()

        model_names = [r[0] for r in rows if r[0] != 'Standalone / Not Linked']
        display = {}
        if model_names:
            for rec in self.env['ir.model'].sudo().search_read(
                [('model', 'in', model_names)], ['model', 'name']
            ):
                display[rec['model']] = rec['name']

        return [{
            'model': model,
            'label': display.get(model, model),
            'count': count,
            'size_mb': _mb(size),
        } for model, count, size in rows]

    @api.model
    def action_db_size(self):
        self.env.cr.execute(
            "SELECT pg_size_pretty(pg_database_size(current_database())), "
            "pg_database_size(current_database())"
        )
        pretty, raw_bytes = self.env.cr.fetchone()
        return {'pretty': pretty, 'mb': _mb(raw_bytes)}

    @api.model
    def action_find_duplicates(self, limit=200):
        """Attachments sharing identical file content (same checksum).

        NOTE: Odoo's filestore is content-addressed - the physical file for
        a checksum is only deleted once the LAST referencing row is removed,
        so cleaning duplicate rows mainly reduces DB clutter, not disk usage.
        """
        self.env.cr.execute("""
            SELECT checksum, array_agg(id ORDER BY create_date DESC),
                   COUNT(*), MAX(COALESCE(file_size, 0))
            FROM ir_attachment
            WHERE checksum IS NOT NULL AND checksum != ''
            GROUP BY checksum
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT %s
        """, (limit,))
        groups = []
        for checksum, ids, count, size in self.env.cr.fetchall():
            groups.append({
                'checksum': checksum[:12],
                'keep_id': ids[0],
                'remove_ids': ids[1:],
                'count': count,
                'size_mb': _mb(size),
            })
        return groups

    @api.model
    def action_dedupe_all(self, groups=None):
        """Keep the newest record in each duplicate group, remove the rest."""
        if not groups:
            groups = self.action_find_duplicates(limit=2000)
        remove_ids = [rid for g in groups for rid in g['remove_ids']]
        atts = self.env['ir.attachment'].sudo().browse(remove_ids).exists()
        count = len(atts)
        atts.unlink()
        self._log('duplicate', 0.0, count)
        return {'cleared_count': count}

    @api.model
    def action_full_scan(self):
        """Single call powering the dashboard: report + extras + settings."""
        report = self.action_generate_report()
        top_models = self.action_top_models()
        db_size = self.action_db_size()
        dup_groups = self.action_find_duplicates(limit=500)
        settings = self.action_get_settings()
        return {
            **report,
            'top_models': top_models,
            'db_size_pretty': db_size['pretty'],
            'db_size_mb': db_size['mb'],
            'duplicate_groups': len(dup_groups),
            'duplicate_extra_records': sum(len(g['remove_ids']) for g in dup_groups),
            **settings,
        }

    # ---------------------------------------------------------------
    # Drill-down: list individual files in a category
    # ---------------------------------------------------------------
    @api.model
    def action_list_attachments(self, category, limit=500):
        if category not in CONTENT_CATEGORIES:
            return []

        orphaned_ids = set(self._find_orphaned_attachments().ids)

        self.env.cr.execute("""
            SELECT id, name, mimetype, COALESCE(file_size, 0), create_date, res_model
            FROM ir_attachment
            ORDER BY file_size DESC NULLS LAST
        """)

        result = []
        for att_id, name, mimetype, size, create_date, res_model in self.env.cr.fetchall():
            if _categorize(mimetype) != category:
                continue
            result.append({
                'id': att_id,
                'name': name or '(unnamed)',
                'res_model': res_model or 'Standalone / not linked',
                'create_date': create_date.strftime('%Y-%m-%d %H:%M') if create_date else '',
                'size_mb': _mb(size),
                'is_junk': att_id in orphaned_ids,
            })
            if len(result) >= limit:
                break
        return result

    @api.model
    def action_delete_attachments(self, attachment_ids):
        atts = self.env['ir.attachment'].sudo().browse(attachment_ids).exists()
        before_bytes = sum(atts.mapped('file_size'))
        count = len(atts)
        atts.unlink()

        freed_mb = _mb(before_bytes)
        self._log('manual', freed_mb, count)
        _logger.info("Ow Cache Manager: manually deleted %s attachments, freed %s MB", count, freed_mb)
        return {'cleared_count': count, 'freed_mb': freed_mb}

    # ---------------------------------------------------------------
    # Clear actions
    # ---------------------------------------------------------------
    @api.model
    def action_clear_asset_cache(self):
        atts = self.env['ir.attachment'].sudo().search(self._asset_cache_domain())
        before_bytes = sum(atts.mapped('file_size'))
        count = len(atts)
        atts.unlink()

        self.env['ir.attachment'].clear_caches()  # in-memory ormcache / qweb template cache

        freed_mb = _mb(before_bytes)
        self._log('asset_cache', freed_mb, count)
        _logger.info("Ow Cache Manager: cleared %s asset attachments, freed %s MB", count, freed_mb)
        return {'cleared_count': count, 'freed_mb': freed_mb}

    @api.model
    def action_clear_orphaned(self):
        atts = self._find_orphaned_attachments()
        before_bytes = sum(atts.mapped('file_size'))
        count = len(atts)
        atts.unlink()

        freed_mb = _mb(before_bytes)
        self._log('orphaned', freed_mb, count)
        _logger.info("Ow Cache Manager: cleared %s orphaned attachments, freed %s MB", count, freed_mb)
        return {'cleared_count': count, 'freed_mb': freed_mb}

    @api.model
    def action_clear_all(self):
        asset_res = self.action_clear_asset_cache()
        orphan_res = self.action_clear_orphaned()
        return {
            'freed_mb': round(asset_res['freed_mb'] + orphan_res['freed_mb'], 2),
            'cleared_count': asset_res['cleared_count'] + orphan_res['cleared_count'],
            'asset_freed_mb': asset_res['freed_mb'],
            'orphan_freed_mb': orphan_res['freed_mb'],
        }

    # ---------------------------------------------------------------
    # Auto-clean settings + cron
    # ---------------------------------------------------------------
    @api.model
    def action_get_settings(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param(AUTO_CLEAN_PARAM, 'False') == 'True'
        return {'auto_clean_enabled': enabled}

    @api.model
    def action_set_auto_clean(self, enabled):
        self.env['ir.config_parameter'].sudo().set_param(AUTO_CLEAN_PARAM, 'True' if enabled else 'False')
        return {'auto_clean_enabled': bool(enabled)}

    @api.model
    def action_cron_auto_clean(self):
        """Runs daily via ir.cron. Only clears asset cache + orphaned junk -
        never touches live/duplicate data automatically."""
        enabled = self.env['ir.config_parameter'].sudo().get_param(AUTO_CLEAN_PARAM, 'False') == 'True'
        if not enabled:
            return
        res = self.action_clear_all()
        _logger.info("Ow Cache Manager: scheduled auto-clean freed %s MB", res['freed_mb'])

    # ---------------------------------------------------------------
    # Excel export
    # ---------------------------------------------------------------
    @api.model
    def action_export_excel(self):
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_("xlsxwriter is not available on this server."))

        report = self.action_generate_report()
        top_models = self.action_top_models()
        dup_groups = self.action_find_duplicates(limit=100)
        db_size = self.action_db_size()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        bold = workbook.add_format({'bold': True})
        mb_fmt = workbook.add_format({'num_format': '#,##0.00'})

        ws = workbook.add_worksheet('Summary')
        ws.write(0, 0, 'Cache & Storage Report', bold)
        ws.write(1, 0, 'Generated')
        ws.write(1, 1, fields.Datetime.now().strftime('%Y-%m-%d %H:%M'))
        ws.write(2, 0, 'Database Size')
        ws.write(2, 1, db_size['pretty'])
        rows = [
            ('Total Storage (MB)', report['total_mb']),
            ('Asset Cache - regenerable (MB)', report['asset_cache_mb']),
            ('Orphaned Junk (MB)', report['orphaned_mb']),
            ('Images (MB)', report['image_mb']),
            ('Videos (MB)', report['video_mb']),
            ('Documents (MB)', report['document_mb']),
            ('Audio (MB)', report['audio_mb']),
            ('Other (MB)', report['other_mb']),
        ]
        r = 4
        ws.write(r, 0, 'Metric', bold)
        ws.write(r, 1, 'Value', bold)
        for label, val in rows:
            r += 1
            ws.write(r, 0, label)
            ws.write(r, 1, val, mb_fmt)
        ws.set_column(0, 0, 30)
        ws.set_column(1, 1, 16)

        ws2 = workbook.add_worksheet('Top Models')
        ws2.write_row(0, 0, ['Model', 'Files', 'Size (MB)'], bold)
        for i, row in enumerate(top_models, start=1):
            ws2.write(i, 0, row['label'])
            ws2.write(i, 1, row['count'])
            ws2.write(i, 2, row['size_mb'], mb_fmt)
        ws2.set_column(0, 0, 30)

        ws3 = workbook.add_worksheet('Duplicate Records')
        ws3.write(0, 0, 'Note: file content is stored once on disk; removing', bold)
        ws3.write(1, 0, 'duplicate rows mainly reduces DB clutter, not disk usage.')
        ws3.write_row(3, 0, ['Checksum', 'Copies', 'Size Each (MB)'], bold)
        for i, g in enumerate(dup_groups, start=4):
            ws3.write(i, 0, g['checksum'])
            ws3.write(i, 1, g['count'])
            ws3.write(i, 2, g['size_mb'], mb_fmt)
        ws3.set_column(0, 0, 20)

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'Cache_Report_%s.xlsx' % fields.Date.today(),
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': False,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {'url': '/web/content/%s?download=true' % attachment.id}
