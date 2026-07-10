/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

// Hard cap on rendered rows/columns so a huge spreadsheet can't freeze the
// browser tab. The full file is always one click away via "Download".
const QG_MAX_ROWS = 500;
const QG_MAX_COLS = 60;

/**
 * QuickGlancePreviewDialog
 * -------------------------
 * Generic preview popup used both for:
 *  - PDF reports / attachments -> rendered in an <iframe> pointing at Odoo's
 *    bundled pdf.js viewer (same technique the native chatter preview uses).
 *  - Excel (.xlsx/.xls), CSV and ODS files -> parsed client-side with the
 *    bundled SheetJS library and rendered as a plain HTML table built with
 *    OWL's auto-escaping `t-esc`, never with raw/innerHTML injection, so a
 *    booby-trapped spreadsheet cell can't run script in the preview.
 *
 * Props:
 *  - title (String)
 *  - kind ("pdf" | "xlsx" | "xls" | "csv" | "ods")
 *  - pdfViewerUrl (String, required when kind === "pdf")
 *  - contentUrl (String, optional): server URL to fetch raw bytes from for
 *    spreadsheet kinds (e.g. "/web/content/<id>?download=true")
 *  - base64Data (String, optional): base64-encoded bytes, used instead of
 *    contentUrl when the data is already available client-side (e.g. a
 *    Binary field that hasn't been saved to the server yet)
 *  - onDownload (Function, optional): called when the user clicks Download
 *  - close (Function): called when the dialog should be dismissed
 */
export class QuickGlancePreviewDialog extends Component {
    static template = "quickglance_preview.PreviewDialog";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        kind: { type: String },
        pdfViewerUrl: { type: String, optional: true },
        contentUrl: { type: String, optional: true },
        base64Data: { type: String, optional: true },
        onDownload: { type: Function, optional: true },
        close: { type: Function },
    };

    setup() {
        this.state = useState({
            loading: this.props.kind !== "pdf",
            error: "",
            sheetNames: [],
            activeSheetIndex: 0,
            rows: [],
            truncatedRows: false,
            truncatedCols: false,
        });

        if (this.props.kind !== "pdf") {
            onWillStart(() => this._loadSpreadsheet());
        }
    }

    get isPdf() {
        return this.props.kind === "pdf";
    }

    async _loadSpreadsheet() {
        try {
            const XLSX = window.XLSX;
            if (!XLSX) {
                this.state.error = _t("Preview library failed to load. Please refresh and try again.");
                this.state.loading = false;
                return;
            }
            let workbook;
            if (this.props.base64Data) {
                workbook = XLSX.read(this.props.base64Data, { type: "base64" });
            } else if (this.props.contentUrl) {
                const response = await fetch(this.props.contentUrl);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const buffer = await response.arrayBuffer();
                workbook = XLSX.read(new Uint8Array(buffer), { type: "array" });
            } else {
                throw new Error("No data source provided");
            }
            this.workbook = workbook;
            this.state.sheetNames = workbook.SheetNames || [];
            this._renderSheet(0);
        } catch (error) {
            console.error("QuickGlance preview error", error);
            this.state.error = _t("This file could not be previewed. It may be corrupted or in an unsupported format.");
        } finally {
            this.state.loading = false;
        }
    }

    _renderSheet(index) {
        if (!this.workbook || !this.state.sheetNames[index]) {
            return;
        }
        const XLSX = window.XLSX;
        const sheet = this.workbook.Sheets[this.state.sheetNames[index]];
        const json = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: false, defval: "" });
        const truncatedRows = json.length > QG_MAX_ROWS;
        const rows = json.slice(0, QG_MAX_ROWS).map((row) => {
            const truncatedCols = row.length > QG_MAX_COLS;
            const cells = row.slice(0, QG_MAX_COLS).map((cell) => (cell === null || cell === undefined ? "" : String(cell)));
            if (truncatedCols) {
                this.state.truncatedCols = true;
            }
            return cells;
        });
        this.state.activeSheetIndex = index;
        this.state.rows = rows;
        this.state.truncatedRows = truncatedRows;
    }

    selectSheet(index) {
        this._renderSheet(index);
    }

    async onClickDownload() {
        if (this.props.onDownload) {
            await this.props.onDownload();
        }
    }

    onClickClose() {
        this.props.close();
    }
}
