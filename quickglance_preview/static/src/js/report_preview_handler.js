/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { getReportUrl, downloadReport } from "@web/webclient/actions/reports/utils";
import { QuickGlancePreviewDialog } from "./preview_dialog";

/**
 * QuickGlance hooks into Odoo's own "ir.actions.report handlers" registry
 * (the same official extension point Odoo itself uses internally for
 * report actions - see addons/web/static/src/webclient/actions/action_service.js,
 * function _executeReportAction). Returning a truthy value from a handler
 * tells Odoo "this report action has been handled", so the normal
 * auto-download is skipped and QuickGlance's preview is shown instead.
 *
 * This means: no monkey-patching of internal widgets, no version-specific
 * DOM hacks - just the same API Odoo's core uses, which keeps this feature
 * stable across Odoo versions that expose this registry (17.0, 18.0, 19.0).
 *
 * NOTE (18.0/19.0 build only): Odoo removed the old "rpc" service in these
 * versions - env.services.rpc no longer exists at all. downloadReport()
 * must be called with the plain `rpc` function imported above instead. The
 * 17.0 build of this file still uses env.services.rpc, since that service
 * still exists there and the standalone module doesn't.
 */
registry.category("ir.actions.report handlers").add("quickglance_preview_pdf_handler", async (action, options, env) => {
    // Only intercept actual PDF reports. HTML/text reports keep their
    // normal Odoo behaviour.
    if (action.report_type !== "qweb-pdf") {
        return false;
    }
    // Escape hatch: server actions / automations that print in the
    // background can opt out by adding {'qg_skip_preview': True} to the
    // action context, so QuickGlance never interferes with automated flows.
    if (action.context && action.context.qg_skip_preview) {
        return false;
    }

    const pdfUrl = getReportUrl(action, "pdf");
    const viewerUrl = `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(pdfUrl)}#pagemode=none`;

    return new Promise((resolve) => {
        let settled = false;
        const finish = () => {
            if (!settled) {
                settled = true;
                resolve(true);
            }
        };
        env.services.dialog.add(
            QuickGlancePreviewDialog,
            {
                title: action.display_name || action.name || "Report Preview",
                kind: "pdf",
                pdfViewerUrl: viewerUrl,
                onDownload: async () => {
                    await downloadReport(rpc, action, "pdf", action.context || {});
                },
                close: finish,
            },
            { onClose: finish }
        );
    });
});
