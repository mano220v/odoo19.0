/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class ModuleUsageDashboard extends Component {
    static template = "module_usage_tracker.Dashboard";
    static components = { Layout };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        const today = new Date().toISOString().slice(0, 10);
        this.state = useState({
            loading: true,
            period: "today",
            fromDate: today,
            toDate: today,
            userId: 0,
            users: [],
            data: {
                label: "",
                total_seconds: 0,
                total_duration: "0s",
                module_count: 0,
                top_module: "-",
                rows: [],
                users: [],
                recent: [],
                trend: [],
                last_refresh: "",
            },
        });
        onWillStart(async () => {
            await Promise.all([this.loadUsers(), this.loadData()]);
        });
    }

    excludedTrackerDomain() {
        return [
            ["module_name", "not in", ["Module Usage", "Module Usage Dashboard"]],
            ["module_xmlid", "not in", [
                "module_usage_tracker.menu_module_usage_root",
                "module_usage_tracker.menu_module_usage_dashboard",
                "module_usage_tracker.menu_module_usage_logs",
            ]],
        ];
    }

    async loadUsers() {
        this.state.users = await this.orm.searchRead("res.users", [["share", "=", false]], ["name"], { order: "name asc" });
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await rpc("/module_usage_tracker/dashboard_data", {
                period: this.state.period,
                from_date: this.state.fromDate,
                to_date: this.state.toDate,
                user_id: this.state.userId || false,
            });
        } catch (error) {
            this.notification.add("Could not load module usage data.", { type: "danger" });
            console.error("[ModuleUsageDashboard]", error);
        } finally {
            this.state.loading = false;
        }
    }

    async setPeriod(period) {
        this.state.period = period;
        await this.loadData();
    }

    async setUser(ev) {
        this.state.userId = Number(ev.target.value || 0);
        await this.loadData();
    }

    async setDate(field, ev) {
        this.state[field] = ev.target.value;
        this.state.period = "custom";
        await this.loadData();
    }

    rowWidth(row) {
        const first = this.state.data.rows[0];
        if (!first || !first.seconds) {
            return "0%";
        }
        return `${Math.max(3, Math.round((row.seconds / first.seconds) * 100))}%`;
    }

    trendHeight(point) {
        const max = Math.max(...this.state.data.trend.map((item) => item.hours), 0);
        if (!max) {
            return "4%";
        }
        return `${Math.max(6, Math.round((point.hours / max) * 100))}%`;
    }

    openLogs(domain = [], title = "Usage Logs") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "module.usage.log",
            view_mode: "list,graph,pivot,form",
            views: [[false, "list"], [false, "graph"], [false, "pivot"], [false, "form"]],
            domain: [...this.excludedTrackerDomain(), ...domain],
        });
    }

    openAllLogs() {
        this.openLogs([], "All Usage Logs");
    }

    openActiveUserLogs() {
        const domain = this.state.userId ? [["user_id", "=", this.state.userId]] : [];
        this.openLogs(domain, "User Usage Logs");
    }
}

registry.category("actions").add("module_usage_tracker_dashboard", ModuleUsageDashboard);
