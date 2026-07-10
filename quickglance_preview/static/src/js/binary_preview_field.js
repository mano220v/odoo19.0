/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { isBinarySize } from "@web/core/utils/binary";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";
import { QuickGlancePreviewDialog } from "./preview_dialog";

const QG_PREVIEWABLE_EXT = ["pdf", "xlsx", "xls", "csv", "ods"];

export class QuickGlanceBinaryField extends BinaryField {
    static template = "quickglance_preview.BinaryFieldPreview";

    setup() {
        super.setup();
        this.qgDialog = useService("dialog");
    }

    get qgExtension() {
        const name = this.fileName || "";
        return name.includes(".") ? name.split(".").pop().toLowerCase() : "";
    }

    get qgIsPreviewable() {
        return QG_PREVIEWABLE_EXT.includes(this.qgExtension) && !!this.props.record.data[this.props.name];
    }

    async onClickQgPreview() {
        const ext = this.qgExtension;
        const raw = this.props.record.data[this.props.name];
        const kind = ext === "pdf" ? "pdf" : ext;

        // If the field already holds the actual base64 payload (typical in
        // form views), preview it directly - no server round-trip needed,
        // this even works for a file the user just picked and hasn't saved
        // yet. Otherwise (e.g. isBinarySize placeholder in some list
        // contexts), fall back to fetching it from the server.
        const hasInlineData = typeof raw === "string" && raw && !isBinarySize(raw);

        if (kind === "pdf") {
            const pdfSource = hasInlineData
                ? `data:application/pdf;base64,${raw}`
                : this._qgServerUrl();
            const viewerUrl = `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(pdfSource)}#pagemode=none`;
            this.qgDialog.add(QuickGlancePreviewDialog, {
                title: this.fileName,
                kind: "pdf",
                pdfViewerUrl: viewerUrl,
                onDownload: () => this.onFileDownload(),
                close: () => {},
            });
            return;
        }

        this.qgDialog.add(QuickGlancePreviewDialog, {
            title: this.fileName,
            kind,
            base64Data: hasInlineData ? raw : undefined,
            contentUrl: hasInlineData ? undefined : this._qgServerUrl(),
            onDownload: () => this.onFileDownload(),
            close: () => {},
        });
    }

    _qgServerUrl() {
        const { record } = this.props;
        const params = new URLSearchParams({
            model: record.resModel,
            id: record.resId,
            field: this.props.name,
            filename_field: this.props.fileNameField || "",
            download: "true",
        });
        return `/web/content?${params.toString()}`;
    }
}

export const quickGlanceBinaryField = {
    ...binaryField,
    component: QuickGlanceBinaryField,
    displayName: "File (QuickGlance Preview)",
};

registry.category("fields").add("quickglance_preview", quickGlanceBinaryField);
