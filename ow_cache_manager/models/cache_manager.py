import logging

from odoo import api, models

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


class OwCacheManager(models.TransientModel):
    _name = 'ow.cache.manager'
    _description = 'Odoo Cache & Storage Manager'

    # ---------------------------------------------------------------
    # Domains
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
        _logger.info("Ow Cache Manager: cleared %s asset attachments, freed %s MB", count, freed_mb)
        return {'cleared_count': count, 'freed_mb': freed_mb}

    @api.model
    def action_clear_orphaned(self):
        atts = self._find_orphaned_attachments()
        before_bytes = sum(atts.mapped('file_size'))
        count = len(atts)
        atts.unlink()

        freed_mb = _mb(before_bytes)
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
