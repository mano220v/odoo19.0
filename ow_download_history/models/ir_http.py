# -*- coding: utf-8 -*-
"""
Generic, version-stable download tracking.

Rather than overriding individual controller classes (whose method
signatures change across Odoo versions), this hooks into
``ir.http._post_dispatch`` — a stable extension point that runs once
after *every* HTTP request, right before the response is sent to the
browser. From there we inspect the request path and the response
headers to decide whether a file was actually downloaded, and by whom.

This covers the three built-in download channels:
    * /web/content, /web/image      -> attachments
    * /report/download              -> PDF / XLSX / other report formats
    * /web/export/xlsx, /web/export/csv (and similar) -> data exports
"""
import json
import logging
import re

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)

DOWNLOAD_PATH_PREFIXES = ('/web/content', '/web/image', '/report/download', '/web/export/')

_FILENAME_RE = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?')
_REPORT_URL_RE = re.compile(r'/report/(?:pdf|text|html)/([^/?]+)/?([\d,]*)')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_dispatch(cls, response):
        result = super()._post_dispatch(response)
        try:
            cls._ow_track_download(response)
        except Exception:  # never let logging break an actual download
            _logger.exception("ow_download_history: failed to log download")
        return result

    # -- main entry point ------------------------------------------------
    @classmethod
    def _ow_track_download(cls, response):
        httprequest = getattr(request, 'httprequest', None)
        if httprequest is None or response is None:
            return
        path = httprequest.path or ''
        if not path.startswith(DOWNLOAD_PATH_PREFIXES):
            return
        if getattr(response, 'status_code', None) != 200:
            return
        if not getattr(request, 'env', None):
            return

        disposition = response.headers.get('Content-Disposition', '') or ''
        file_type = cls._ow_classify(path)

        # Skip inline previews (kanban thumbnails, embedded PDF viewer, ...):
        # only log attachment/image requests that are real "Download" clicks.
        if file_type in ('attachment', 'image') and 'attachment' not in disposition.lower():
            return

        filename = cls._ow_extract_filename(disposition) or path.rsplit('/', 1)[-1] or file_type
        mimetype = (response.headers.get('Content-Type', '') or '').split(';')[0] or False
        try:
            file_size = int(response.headers.get('Content-Length') or 0)
        except (TypeError, ValueError):
            file_size = 0

        res_model = res_id = res_name = attachment_id = report_id = False
        try:
            if file_type in ('attachment', 'image'):
                res_model, res_id, attachment_id = cls._ow_parse_content(httprequest, path)
            elif file_type == 'report':
                res_model, res_id, report_id = cls._ow_parse_report(httprequest)
            elif file_type == 'export':
                res_model, res_id = cls._ow_parse_export(httprequest)
        except Exception:
            _logger.exception("ow_download_history: could not parse download source")

        if res_model and res_id and res_model in request.env:
            try:
                rec = request.env[res_model].sudo().browse(int(res_id))
                if rec.exists():
                    res_name = rec.display_name
            except Exception:
                res_name = False
        elif res_model and not res_id:
            res_name = res_model

        request.env['ow.download.history'].sudo().log_download(
            file_name=filename,
            file_type=file_type,
            mimetype=mimetype,
            file_size=file_size,
            res_model=res_model or False,
            res_id=int(res_id) if res_id and str(res_id).isdigit() else False,
            res_name=res_name,
            attachment_id=attachment_id or False,
            report_id=report_id or False,
            request=request,
        )

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _ow_classify(path):
        if path.startswith('/web/image'):
            return 'image'
        if path.startswith('/report/download'):
            return 'report'
        if path.startswith('/web/export/'):
            return 'export'
        return 'attachment'

    @staticmethod
    def _ow_extract_filename(disposition):
        if not disposition:
            return False
        match = _FILENAME_RE.search(disposition)
        return match.group(1).strip() if match else False

    @staticmethod
    def _ow_parse_content(httprequest, path):
        """Best-effort extraction of (model, res_id, attachment_id) for
        /web/content and /web/image requests, which Odoo serves either as
        query params or as path segments depending on how the link/widget
        built the URL."""
        model = httprequest.args.get('model')
        res_id = httprequest.args.get('id')
        attachment_id = False

        if not model:
            parts = [p for p in path.split('/') if p]
            # parts = ['web', 'content'|'image', <seg3>, <seg4>, ...]
            if len(parts) > 2:
                seg3 = parts[2]
                if '-' in seg3 and seg3.split('-')[0].isdigit():
                    attachment_id = int(seg3.split('-')[0])
                    model, res_id = 'ir.attachment', attachment_id
                elif seg3.isdigit():
                    attachment_id = int(seg3)
                    model, res_id = 'ir.attachment', attachment_id
                elif len(parts) > 3 and parts[3].isdigit():
                    model, res_id = seg3, int(parts[3])

        if model == 'ir.attachment' and res_id:
            attachment_id = int(res_id)

        res_id = int(res_id) if res_id and str(res_id).isdigit() else False
        return model, res_id, attachment_id

    @staticmethod
    def _ow_parse_report(httprequest):
        report_id = res_model = res_id = False
        raw = httprequest.args.get('data')
        if not raw:
            return res_model, res_id, report_id
        try:
            payload = json.loads(raw)
            url = payload[0] if payload else ''
            match = _REPORT_URL_RE.search(url)
            if match:
                report_ref, doc_ids = match.group(1), match.group(2)
                report = request.env['ir.actions.report'].sudo().search(
                    [('report_name', '=', report_ref)], limit=1)
                if report:
                    report_id, res_model = report.id, report.model
                if doc_ids:
                    first_id = doc_ids.split(',')[0]
                    if first_id.isdigit():
                        res_id = int(first_id)
        except Exception:
            pass
        return res_model, res_id, report_id

    @staticmethod
    def _ow_parse_export(httprequest):
        res_model = False
        raw = httprequest.form.get('data') if httprequest.method == 'POST' else httprequest.args.get('data')
        if raw:
            try:
                payload = json.loads(raw)
                res_model = payload.get('model')
            except Exception:
                pass
        return res_model, False
