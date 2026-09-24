/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class AttachmentListDialog extends Component {
    static components = { Dialog };
    static template = "ow_cache_manager_pro.AttachmentListDialog";
    static props = {
        title: String,
        attachments: Array,
        close: Function,
        onDeleted: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            attachments: this.props.attachments,
            selected: new Set(),
            deleting: false,
            search: "",
            ageFilter: 0,
        });
    }

    filteredList() {
        const q = this.state.search.trim().toLowerCase();
        const now = Date.now();
        return this.state.attachments.filter((a) => {
            if (q && !a.name.toLowerCase().includes(q)) {
                return false;
            }
            if (this.state.ageFilter) {
                const created = new Date(a.create_date.replace(" ", "T")).getTime();
                const ageDays = (now - created) / 86400000;
                if (ageDays < this.state.ageFilter) {
                    return false;
                }
            }
            return true;
        });
    }

    toggle(id) {
        if (this.state.selected.has(id)) {
            this.state.selected.delete(id);
        } else {
            this.state.selected.add(id);
        }
    }

    toggleAll(ev) {
        const visible = this.filteredList();
        if (ev.target.checked) {
            for (const att of visible) {
                this.state.selected.add(att.id);
            }
        } else {
            for (const att of visible) {
                this.state.selected.delete(att.id);
            }
        }
    }

    selectJunkOnly() {
        this.state.selected.clear();
        for (const att of this.filteredList()) {
            if (att.is_junk) {
                this.state.selected.add(att.id);
            }
        }
    }

    fmt(mb) {
        if (mb >= 1024) {
            return (mb / 1024).toFixed(2) + " GB";
        }
        return mb.toFixed(2) + " MB";
    }

    async deleteSelected() {
        if (!this.state.selected.size) {
            return;
        }
        this.state.deleting = true;
        try {
            const ids = [...this.state.selected];
            const res = await this.orm.call("ow.cache.manager.pro", "action_delete_attachments", [ids]);
            this.notification.add(
                `Deleted ${res.cleared_count} file(s), freed ${this.fmt(res.freed_mb)}`,
                { type: "success" }
            );
            this.state.attachments = this.state.attachments.filter((a) => !this.state.selected.has(a.id));
            this.state.selected.clear();
            if (this.props.onDeleted) {
                this.props.onDeleted();
            }
        } catch (e) {
            this.notification.add("Delete failed", { type: "danger" });
        } finally {
            this.state.deleting = false;
        }
    }
}
