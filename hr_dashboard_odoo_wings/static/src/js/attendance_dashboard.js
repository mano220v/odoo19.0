/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
// ─── Auto-refresh interval (ms) ────────────────────────────────────────────
const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

// ─── Dashboard Component ───────────────────────────────────────────────────

class AttendanceDashboard extends Component {
    static template = "hr_dashboard_odoo_wings.AttendanceDashboard";

    setup() {
        this.actionSvc = useService("action");
        this.notif     = useService("notification");

        this.state = useState({
            loading:      true,
            error:        false,
            totalCount:   0,
            presentCount: 0,
            onLeaveCount: 0,
            absentCount:  0,
            presentIds:   [],
            onLeaveIds:   [],
            absentIds:    [],
            todayStart:   "",
            todayEnd:     "",
            todayLabel:   "",
            lastRefresh:  "",
        });

        this._timer = null;

        onMounted(async () => {
            await this.loadData();
            this._timer = setInterval(() => this.loadData(), REFRESH_INTERVAL_MS);
        });

        onWillUnmount(() => {
            if (this._timer) {
                clearInterval(this._timer);
            }
        });
    }

    // ── Data Fetching ──────────────────────────────────────────────────────

    async loadData() {
        this.state.loading = true;
        this.state.error   = false;
        try {
            const data = await rpc(
                "/hr_dashboard_odoo_wings/get_attendance_data",
                {}
            );
            Object.assign(this.state, {
                totalCount:   data.total,
                presentCount: data.present_count,
                onLeaveCount: data.on_leave_count,
                absentCount:  data.absent_count,
                presentIds:   data.present_ids,
                onLeaveIds:   data.on_leave_ids,
                absentIds:    data.absent_ids,
                todayStart:   data.today_start,
                todayEnd:     data.today_end,
                todayLabel:   data.today_label,
                lastRefresh:  new Date().toLocaleTimeString(),
            });
        } catch (err) {
            this.state.error = true;
            console.error("[AttendanceDashboard] Failed to load data", err);
        } finally {
            this.state.loading = false;
        }
    }

    // ── Percentage helpers (used in template) ─────────────────────────────

    pct(count) {
        if (!this.state.totalCount) return 0;
        return Math.round((count / this.state.totalCount) * 100);
    }

    // ── Card Click Handlers ────────────────────────────────────────────────

    openList(type) {
        switch (type) {
            // ── All employees ──────────────────────────────────────────────
            case "all":
                this.actionSvc.doAction({
                    type:      "ir.actions.act_window",
                    name:      "All Employees",
                    res_model: "hr.employee",
                    view_mode: "list,form",
                    views:     [[false, "list"], [false, "form"]],
                    domain:    [["active", "=", true]],
                    context:   { search_default_filter_emp: 1 },
                });
                break;

            // ── Present employees → attendance records today ────────────────
            case "present":
                this.actionSvc.doAction({
                    type:      "ir.actions.act_window",
                    name:      `Present Employees — ${this.state.todayLabel}`,
                    res_model: "hr.attendance",
                    view_mode: "list,form",
                    views:     [
                        [false, "list"],
                        [false, "form"],
                    ],
                    domain: [
                        ["check_in", ">=", this.state.todayStart],
                        ["check_in", "<=", this.state.todayEnd],
                    ],
                    context: {
                        dashboard_present: true,
                    },
                });
                break;

            // ── On Leave → hr.employee filtered by IDs ─────────────────────
            case "on_leave":
                if (!this.state.onLeaveIds.length) {
                    this.notif.add("No employees are on approved leave today.", {
                        type: "info",
                    });
                    return;
                }
                this.actionSvc.doAction({
                    type:      "ir.actions.act_window",
                    name:      `On Leave Today — ${this.state.todayLabel}`,
                    res_model: "hr.employee",
                    view_mode: "list,form",
                    views:     [[false, "list"], [false, "form"]],
                    domain:    [["id", "in", this.state.onLeaveIds]],
                    context:   { dashboard_on_leave: true },
                });
                break;

            // ── Absent → hr.employee filtered by IDs ──────────────────────
            case "absent":
                if (!this.state.absentIds.length) {
                    this.notif.add("All employees are accounted for today!", {
                        type: "success",
                    });
                    return;
                }
                this.actionSvc.doAction({
                    type:      "ir.actions.act_window",
                    name:      `Absent Employees — ${this.state.todayLabel}`,
                    res_model: "hr.employee",
                    view_mode: "list,form",
                    views:     [[false, "list"], [false, "form"]],
                    domain:    [["id", "in", this.state.absentIds]],
                    context:   { dashboard_absent: true },
                });
                break;
        }
    }
}

// ── Register as a client action ────────────────────────────────────────────
registry.category("actions").add(
    "attendance_dashboard_action",
    AttendanceDashboard
);
