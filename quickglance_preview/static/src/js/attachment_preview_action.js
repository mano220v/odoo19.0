/** @odoo-module **/

import { registry } from "@web/core/registry";
import { QuickGlancePreviewDialog } from "./preview_dialog";

/**
 * Function-style client action (see action_service.js: _executeClientAction -
 * "else { const next = await clientAction(env, action, options); }"). No
 * Component/controller is mounted, it just opens the dialog and resolves.
 */
registry.category("actions").add("quickglance_preview.open_attachment", async (env, action) => {
    const params = action.params || {};
    const kind = params.preview_kind;
    const attachmentId = params.attachment_id;

    if (kind === "pdf") {
        const pdfUrl = `/web/content/${attachmentId}`;
        const viewerUrl = `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(pdfUrl)}#pagemode=none`;
        await new Promise((resolve) => {
            env.services.dialog.add(
                QuickGlancePreviewDialog,
                {
                    title: params.name,
                    kind: "pdf",
                    pdfViewerUrl: viewerUrl,
                    onDownload: () => {
                        window.location = `/web/content/${attachmentId}?download=true`;
                    },
                    close: () => resolve(),
                },
                { onClose: () => resolve() }
            );
        });
        return;
    }

    // Spreadsheet-like kinds: xlsx, xls, csv, ods
    await new Promise((resolve) => {
        env.services.dialog.add(
            QuickGlancePreviewDialog,
            {
                title: params.name,
                kind: kind,
                contentUrl: `/web/content/${attachmentId}?download=true`,
                onDownload: () => {
                    window.location = `/web/content/${attachmentId}?download=true`;
                },
                close: () => resolve(),
            },
            { onClose: () => resolve() }
        );
    });
});
