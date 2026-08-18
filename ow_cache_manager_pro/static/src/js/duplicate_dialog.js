/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class DuplicateDialog extends Component {
    static components = { Dialog };
    static template = "ow_cache_manager_pro.DuplicateDialog";
    static props = {
        close: Function,
        onCleaned: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ loading: true, groups: [], cleaning: false });

        onWillStart(async () => {
            this.state.groups = await this.orm.call("ow.cache.manager.pro", "action_find_duplicates", []);
            this.state.loading = false;
        });
    }

    async cleanAll() {
        this.state.cleaning = true;
        try {
            const res = await this.orm.call("ow.cache.manager.pro", "action_dedupe_all", [this.state.groups]);
            this.notification.add(`Removed ${res.cleared_count} duplicate record(s)`, { type: "success" });
            if (this.props.onCleaned) {
                this.props.onCleaned();
            }
            this.props.close();
        } catch (e) {
            this.notification.add("Cleanup failed", { type: "danger" });
        } finally {
            this.state.cleaning = false;
        }
    }
}
