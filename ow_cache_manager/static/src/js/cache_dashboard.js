/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { AttachmentListDialog } from "./attachment_list_dialog";

const CATEGORY_LABELS = {
    image: "Images",
    video: "Videos",
    document: "Documents",
    audio: "Audio",
    other: "Other Files",
};

class CacheManagerDashboard extends Component {
    static template = "ow_cache_manager.Dashboard";

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
            last_freed_mb: null,
            last_cleared_count: null,
        });

        onWillStart(() => this.generate());
    }

    async generate() {
        this.state.loading = true;
        try {
            const res = await this.orm.call("ow.cache.manager", "action_generate_report", []);
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
            const res = await this.orm.call("ow.cache.manager", method, []);
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
            attachments = await this.orm.call("ow.cache.manager", "action_list_attachments", [category]);
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

registry.category("actions").add("ow_cache_manager_dashboard", CacheManagerDashboard);
