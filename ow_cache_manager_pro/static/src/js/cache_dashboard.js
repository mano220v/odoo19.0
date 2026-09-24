/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { AttachmentListDialog } from "./attachment_list_dialog";
import { DuplicateDialog } from "./duplicate_dialog";

const CATEGORY_LABELS = {
    image: "Images",
    video: "Videos",
    document: "Documents",
    audio: "Audio",
    other: "Other Files",
};

class CacheManagerDashboard extends Component {
    static template = "ow_cache_manager_pro.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            loading: false,
            clearing: false,
            scanned: false,
            total_mb: 0,
            asset_cache_mb: 0,
            asset_count: 0,
            orphaned_mb: 0,
            orphaned_count: 0,
            image_mb: 0,
            video_mb: 0,
            document_mb: 0,
            audio_mb: 0,
            other_mb: 0,
            top_models: [],
            db_size_pretty: "",
            db_size_mb: 0,
            duplicate_groups: 0,
            duplicate_extra_records: 0,
            auto_clean_enabled: false,
            exporting: false,
            last_freed_mb: null,
            last_cleared_count: null,
        });

        onWillStart(() => this.generate());
    }

    async generate() {
        this.state.loading = true;
        try {
            const res = await this.orm.call("ow.cache.manager.pro", "action_full_scan", []);
            Object.assign(this.state, res);
            this.state.scanned = true;
        } catch (e) {
            this.notification.add(this._errMsg(e, "Failed to scan cache"), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    clearAssets() {
        return this._clear("action_clear_asset_cache", "Asset cache cleared");
    }

    clearOrphaned() {
        return this._clear("action_clear_orphaned", "Junk files removed");
    }

    clearAll() {
        return this._clear("action_clear_all", "Full cleanup complete");
    }

    async _clear(method, successMsg) {
        this.state.clearing = true;
        try {
            const res = await this.orm.call("ow.cache.manager.pro", method, []);
            this.state.last_freed_mb = res.freed_mb;
            this.state.last_cleared_count = res.cleared_count;
            this.notification.add(`${successMsg} - freed ${this.fmt(res.freed_mb)}`, { type: "success" });
            await this.generate();
        } catch (e) {
            this.notification.add(this._errMsg(e, "Clear failed"), { type: "danger" });
        } finally {
            this.state.clearing = false;
        }
    }

    async openCategory(category) {
        let attachments;
        try {
            attachments = await this.orm.call("ow.cache.manager.pro", "action_list_attachments", [category]);
        } catch (e) {
            this.notification.add(this._errMsg(e, "Failed to load files"), { type: "danger" });
            return;
        }
        this.dialog.add(AttachmentListDialog, {
            title: CATEGORY_LABELS[category] || category,
            attachments,
            onDeleted: () => this.generate(),
        });
    }

    openDuplicates() {
        this.dialog.add(DuplicateDialog, {
            onCleaned: () => this.generate(),
        });
    }

    async toggleAutoClean(ev) {
        const enabled = ev.target.checked;
        try {
            await this.orm.call("ow.cache.manager.pro", "action_set_auto_clean", [enabled]);
            this.state.auto_clean_enabled = enabled;
            this.notification.add(
                enabled ? "Auto-clean enabled (runs daily)" : "Auto-clean disabled",
                { type: "success" }
            );
        } catch (e) {
            this.notification.add(this._errMsg(e, "Failed to update setting"), { type: "danger" });
        }
    }

    async exportExcel() {
        this.state.exporting = true;
        try {
            const res = await this.orm.call("ow.cache.manager.pro", "action_export_excel", []);
            window.open(res.url, "_blank");
        } catch (e) {
            this.notification.add(this._errMsg(e, "Export failed"), { type: "danger" });
        } finally {
            this.state.exporting = false;
        }
    }

    get chartGradient() {
        const cats = [
            { mb: this.state.image_mb, color: "#4a90d9" },
            { mb: this.state.video_mb, color: "#e0574c" },
            { mb: this.state.document_mb, color: "#f5a623" },
            { mb: this.state.audio_mb, color: "#7ed321" },
            { mb: this.state.other_mb, color: "#9b9b9b" },
        ];
        const total = cats.reduce((s, c) => s + c.mb, 0) || 1;
        let acc = 0;
        const stops = cats.map((c) => {
            const start = (acc / total) * 360;
            acc += c.mb;
            const end = (acc / total) * 360;
            return `${c.color} ${start}deg ${end}deg`;
        });
        return `conic-gradient(${stops.join(", ")})`;
    }

    _errMsg(e, fallback) {
        return (e && e.data && e.data.message) || e.message || fallback;
    }

    fmt(mb) {
        if (mb === undefined || mb === null) {
            return "0 MB";
        }
        if (mb >= 1024) {
            return (mb / 1024).toFixed(2) + " GB";
        }
        return mb.toFixed(2) + " MB";
    }

    barWidth(mb) {
        const max = Math.max(
            this.state.image_mb,
            this.state.video_mb,
            this.state.document_mb,
            this.state.audio_mb,
            this.state.other_mb,
            1
        );
        return Math.max(2, Math.round((mb / max) * 100)) + "%";
    }
}

registry.category("actions").add("ow_cache_manager_dashboard_pro", CacheManagerDashboard);
