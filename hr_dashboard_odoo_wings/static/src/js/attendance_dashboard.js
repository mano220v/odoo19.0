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
		            departments:  [],   // [{id, name, total, present_count, on_leave_count, absent_count, ...}]
		            todayStart:   "",
		            todayEnd:     "",
		            todayLabel:   "",
		            lastRefresh:  "",

		            // ── Export modal state ──────────────────────────────────────
		            showExportModal: false,
		            exportDateType:  "current",   // "current" | "range"
		            exportFromDate:  "",
		            exportToDate:    "",
		            exportError:     "",
		            exporting:       false,
		        });

		        this._timer = null;

		        onMounted(async () => {
		            await this.loadData();
		            this._timer = setInterval(() => this.loadData(), REFRESH_INTERVAL_MS);
		        });

		        onWillUnmount(() => {
		            if (this._timer) clearInterval(this._timer);
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
		                departments:  data.departments  || [],
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

		    // ── Helpers ────────────────────────────────────────────────────────────

		    pct(count, total) {
		        const t = total !== undefined ? total : this.state.totalCount;
		        if (!t) return 0;
		        return Math.round((count / t) * 100);
		    }

		    // ── Global card click handlers ─────────────────────────────────────────

		    openList(type) {
		        switch (type) {
		            case "all":
		                this.actionSvc.doAction({
		                    type: "ir.actions.act_window",
		                    name: "All Employees",
		                    res_model: "hr.employee",
		                    view_mode: "list,form",
		                    views: [[false, "list"], [false, "form"]],
		                    domain: [["active", "=", true]],
		                });
		                break;

		            case "present":
		                this.actionSvc.doAction({
		                    type: "ir.actions.act_window",
		                    name: `Present Employees — ${this.state.todayLabel}`,
		                    res_model: "hr.attendance",
		                    view_mode: "list,form",
		                    views: [[false, "list"], [false, "form"]],
		                    domain: [
		                        ["check_in", ">=", this.state.todayStart],
		                        ["check_in", "<=", this.state.todayEnd],
		                    ],
		                });
		                break;

		            case "on_leave":
		                if (!this.state.onLeaveIds.length) {
		                    this.notif.add("No employees are on approved leave today.", { type: "info" });
		                    return;
		                }
		                this.actionSvc.doAction({
		                    type: "ir.actions.act_window",
		                    name: `On Leave Today — ${this.state.todayLabel}`,
		                    res_model: "hr.employee",
		                    view_mode: "list,form",
		                    views: [[false, "list"], [false, "form"]],
		                    domain: [["id", "in", this.state.onLeaveIds]],
		                });
		                break;

		            case "absent":
		                if (!this.state.absentIds.length) {
		                    this.notif.add("All employees are accounted for today!", { type: "success" });
		                    return;
		                }
		                this.actionSvc.doAction({
		                    type: "ir.actions.act_window",
		                    name: `Absent Employees — ${this.state.todayLabel}`,
		                    res_model: "hr.employee",
		                    view_mode: "list,form",
		                    views: [[false, "list"], [false, "form"]],
		                    domain: [["id", "in", this.state.absentIds]],
		                });
		                break;
		        }
		    }

		    // ── Department drilldown click handler ────────────────────────────────
		    // type: "present" | "on_leave" | "absent" | "all"

		    openDeptList(dept, type) {
		        const labels = {
		            present:  "Present",
		            on_leave: "On Leave",
		            absent:   "Absent",
		            all:      "All",
		        };
		        const label = labels[type] || type;
		        const title = `${dept.name} — ${label} (${this.state.todayLabel})`;

		        // For "present" we open hr.attendance (shows check-in/out)
		        // For everything else we open hr.employee
		        if (type === "present") {
		            const ids = dept.present_ids || [];
		            if (!ids.length) {
		                this.notif.add(`No present employees in ${dept.name} today.`, { type: "info" });
		                return;
		            }
		            this.actionSvc.doAction({
		                type: "ir.actions.act_window",
		                name: title,
		                res_model: "hr.attendance",
		                view_mode: "list,form",
		                views: [[false, "list"], [false, "form"]],
		                domain: [
		                    ["check_in",    ">=", this.state.todayStart],
		                    ["check_in",    "<=", this.state.todayEnd],
		                    ["employee_id", "in", ids],
		                ],
		            });
		            return;
		        }

		        let ids = [];
		        if (type === "on_leave") ids = dept.on_leave_ids || [];
		        else if (type === "absent")  ids = dept.absent_ids  || [];
		        else if (type === "all")     ids = [
		            ...(dept.present_ids  || []),
		            ...(dept.on_leave_ids || []),
		            ...(dept.absent_ids   || []),
		        ];

		        if (!ids.length) {
		            this.notif.add(`No ${label.toLowerCase()} employees in ${dept.name} today.`, { type: "info" });
		            return;
		        }

		        this.actionSvc.doAction({
		            type: "ir.actions.act_window",
		            name: title,
		            res_model: "hr.employee",
		            view_mode: "list,form",
		            views: [[false, "list"], [false, "form"]],
		            domain: [["id", "in", ids]],
		        });
		    }
		    // ── Export modal: open / close ────────────────────────────────────────

		    openExportModal() {
		        const todayStr = new Date().toISOString().slice(0, 10);
		        this.state.showExportModal = true;
		        this.state.exportDateType  = "current";
		        this.state.exportFromDate  = todayStr;
		        this.state.exportToDate    = todayStr;
		        this.state.exportError     = "";
		    }

		    closeExportModal() {
		        if (this.state.exporting) return;  // don't allow closing mid-export
		        this.state.showExportModal = false;
		    }

		    setExportDateType(type) {
		        this.state.exportDateType = type;
		        this.state.exportError    = "";
		    }

		    // ── Export modal: confirm & trigger download ────────────────────────────

		    confirmExport() {
		        this.state.exportError = "";

		        const params = new URLSearchParams();

		        if (this.state.exportDateType === "current") {
		            params.set("date_type", "current");
		        } else {
		            const from = this.state.exportFromDate;
		            const to   = this.state.exportToDate;
		            if (!from || !to) {
		                this.state.exportError = "Please select both From and To dates.";
		                return;
		            }
		            params.set("date_type", "range");
		            params.set("from_date", from);
		            params.set("to_date", to);
		        }

		        this.state.exporting = true;

		        // Trigger browser download via hidden link (keeps SPA state intact)
		        const url = `/hr_dashboard_odoo_wings/export_attendance?${params.toString()}`;
		        const link = document.createElement("a");
		        link.href = url;
		        link.target = "_blank";
		        document.body.appendChild(link);
		        link.click();
		        document.body.removeChild(link);

		        // Give the browser a moment to start the download, then close modal
		        setTimeout(() => {
		            this.state.exporting       = false;
		            this.state.showExportModal = false;
		            this.notif.add("Export started — check your downloads.", { type: "success" });
		        }, 600);
		    }
		}

		registry.category("actions").add("attendance_dashboard_action", AttendanceDashboard);
