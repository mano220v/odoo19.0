# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Mimetypes QuickGlance knows how to render itself (client-side).
# Note: Odoo's native chatter/file viewer (web/core/file_viewer) only
# handles images, pdf, video and plain text - spreadsheets are NOT
# natively viewable, clicking them in the chatter currently does nothing.
QG_PDF_MIMETYPES = {"application/pdf"}
QG_SPREADSHEET_MIMETYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.ms-excel",  # xls
    "text/csv",
    "application/csv",
    "application/vnd.oasis.opendocument.spreadsheet",  # ods
}
QG_EXT_TO_KIND = {
    "pdf": "pdf",
    "xlsx": "xlsx",
    "xls": "xls",
    "csv": "csv",
    "ods": "ods",
}


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    qg_preview_kind = fields.Selection(
        selection=[
            ("pdf", "PDF"),
            ("xlsx", "Excel (.xlsx)"),
            ("xls", "Excel (.xls)"),
            ("csv", "CSV"),
            ("ods", "OpenDocument Spreadsheet"),
            ("none", "Not previewable"),
        ],
        string="QuickGlance Preview Type",
        compute="_compute_qg_preview_kind",
        store=False,
    )
    qg_is_previewable = fields.Boolean(
        string="QuickGlance Previewable",
        compute="_compute_qg_preview_kind",
        store=False,
    )

    @api.depends("mimetype", "name")
    def _compute_qg_preview_kind(self):
        for rec in self:
            kind = None
            if rec.mimetype in QG_PDF_MIMETYPES:
                kind = "pdf"
            elif rec.mimetype in QG_SPREADSHEET_MIMETYPES:
                # disambiguate xls vs xlsx vs csv vs ods by extension when possible
                ext = rec._qg_extension()
                kind = QG_EXT_TO_KIND.get(ext, "xlsx")
            if not kind:
                # fall back to filename extension (some clients send generic
                # mimetypes like application/octet-stream on upload)
                ext = rec._qg_extension()
                kind = QG_EXT_TO_KIND.get(ext)
            rec.qg_preview_kind = kind or "none"
            rec.qg_is_previewable = bool(kind)

    def _qg_extension(self):
        self.ensure_one()
        if self.name and "." in self.name:
            return self.name.rsplit(".", 1)[-1].lower()
        return ""

    def action_qg_open_preview(self):
        """Return a client action opening the QuickGlance preview dialog
        for this attachment. Can be called from a button anywhere
        ir.attachment records are shown (list/kanban/form/chatter)."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "quickglance_preview.open_attachment",
            "params": {
                "attachment_id": self.id,
                "name": self.name,
                "mimetype": self.mimetype,
                "preview_kind": self.qg_preview_kind,
            },
        }
