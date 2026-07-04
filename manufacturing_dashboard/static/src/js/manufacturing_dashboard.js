/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";

export class ManufacturingDashboard extends Component {
    static template = "manufacturing_dashboard.Dashboard";
    static components = { Layout };
    
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartCanvas = useRef("chartCanvas");
        this.chart = null;

        this.state = useState({
            loading: true,
            period: "today",
            kpi: {
                totalMO: 0, inProgressMO: 0, lateMO: 0, doneTodayMO: 0,
                totalWO: 0, progressWO: 0, pendingWO: 0, lateWO: 0,
            },
            extra: {
                shortage: null, shortageDomain: [],
                scrap: null, scrapDomain: [],
                onTimeRate: null, onTimeDomain: [],
                bomCount: null,
                quality: null, qualityDomain: [],
                maintenance: null, maintenanceDomain: [],
            },
            workcenters: [],
            delayed: [],
            trend: { labels: [], counts: [] },
            lastRefresh: null,
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(async () => {
            await this.loadTrend();
        });

        this.refreshTimer = setInterval(() => this.refreshAll(), 30000);
        onWillUnmount(() => {
            clearInterval(this.refreshTimer);
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    async refreshAll() {
        await this.loadData();
        await this.loadTrend();
    }

    // ---------- date helpers ----------
    toOdooDatetime(d) {
        return d.toISOString().slice(0, 19).replace("T", " ");
    }

    nowStr() {
        return this.toOdooDatetime(new Date());
    }

    startOfDayStr() {
        const d = new Date();
        d.setHours(0, 0, 0, 0);
        return this.toOdooDatetime(d);
    }

    periodStartStr() {
        const now = new Date();
        if (this.state.period === "today") {
            now.setHours(0, 0, 0, 0);
            return this.toOdooDatetime(now);
        }
        if (this.state.period === "week") {
            const day = now.getDay() || 7;
            now.setHours(0, 0, 0, 0);
            now.setDate(now.getDate() - day + 1);
            return this.toOdooDatetime(now);
        }
        if (this.state.period === "month") {
            now.setDate(1);
            now.setHours(0, 0, 0, 0);
            return this.toOdooDatetime(now);
        }
        return null;
    }

    getPeriodDomainFor(field) {
        const start = this.periodStartStr();
        return start ? [[field, ">=", start]] : [];
    }

    // ---------- data loading ----------
    async loadData() {
        this.state.loading = true;
        const periodDomain = this.getPeriodDomainFor("date_start");
        const now = this.nowStr();
        const startOfDay = this.startOfDayStr();

        const [
            totalMO, inProgressMO, lateMO, doneTodayMO,
            totalWO, progressWO, pendingWO, lateWO,
        ] = await Promise.all([
            this.orm.searchCount("mrp.production", [["state", "!=", "cancel"], ...periodDomain]),
            this.orm.searchCount("mrp.production", [["state", "=", "progress"], ...periodDomain]),
            this.orm.searchCount("mrp.production", [["state", "not in", ["done", "cancel"]], ["date_start", "<", now]]),
            this.orm.searchCount("mrp.production", [["state", "=", "done"], ["date_finished", ">=", startOfDay]]),
            this.orm.searchCount("mrp.workorder", [["state", "not in", ["done", "cancel"]], ...periodDomain]),
            this.orm.searchCount("mrp.workorder", [["state", "=", "progress"]]),
            this.orm.searchCount("mrp.workorder", [["state", "in", ["pending", "ready"]]]),
            this.orm.searchCount("mrp.workorder", [["state", "not in", ["done", "cancel"]], ["date_start", "<", now]]),
        ]);

        this.state.kpi = { totalMO, inProgressMO, lateMO, doneTodayMO, totalWO, progressWO, pendingWO, lateWO };

        await Promise.all([
            this.loadShortage(),
            this.loadScrap(),
            this.loadOnTimeRate(),
            this.loadBom(),
            this.loadQuality(),
            this.loadMaintenance(),
        ]);

        const wcGroups = await this.orm.call(
            "mrp.workorder",
            "read_group",
            [[["state", "not in", ["done", "cancel"]]], ["workcenter_id"], ["workcenter_id"]]
        );
        this.state.workcenters = wcGroups
            .filter((g) => g.workcenter_id)
            .map((g) => ({
                id: g.workcenter_id[0],
                name: g.workcenter_id[1],
                count: g.__count !== undefined ? g.__count : g.workcenter_id_count,
            }))
            .sort((a, b) => b.count - a.count)
            .slice(0, 8);

        this.state.delayed = await this.orm.searchRead(
            "mrp.production",
            [["state", "not in", ["done", "cancel"]], ["date_start", "<", now]],
            ["name", "product_id", "date_start", "state"],
            { order: "date_start asc", limit: 6 }
        );

        this.state.lastRefresh = new Date().toLocaleTimeString();
        this.state.loading = false;
    }

    async loadShortage() {
        try {
            const domain = [["state", "not in", ["done", "cancel"]], ["components_availability_state", "in", ["late", "unavailable"]]];
            this.state.extra.shortage = await this.orm.searchCount("mrp.production", domain);
            this.state.extra.shortageDomain = domain;
        } catch (e) {
            this.state.extra.shortage = null;
        }
    }

    async loadScrap() {
        try {
            const domain = [["production_id", "!=", false], ...this.getPeriodDomainFor("create_date")];
            this.state.extra.scrap = await this.orm.searchCount("stock.scrap", domain);
            this.state.extra.scrapDomain = domain;
        } catch (e) {
            this.state.extra.scrap = null;
        }
    }

    async loadOnTimeRate() {
        try {
            const domain = [["state", "=", "done"], ...this.getPeriodDomainFor("date_finished")];
            const records = await this.orm.searchRead("mrp.production", domain, ["date_planned_finish", "date_finished"], { limit: 500 });
            this.state.extra.onTimeDomain = domain;
            if (!records.length) {
                this.state.extra.onTimeRate = null;
                return;
            }
            let onTime = 0;
            for (const r of records) {
                if (!r.date_planned_finish || (r.date_finished && r.date_finished <= r.date_planned_finish)) {
                    onTime++;
                }
            }
            this.state.extra.onTimeRate = Math.round((onTime / records.length) * 100);
        } catch (e) {
            this.state.extra.onTimeRate = null;
        }
    }

    async loadBom() {
        try {
            this.state.extra.bomCount = await this.orm.searchCount("mrp.bom", []);
        } catch (e) {
            this.state.extra.bomCount = null;
        }
    }

    async loadQuality() {
        try {
            const domain = [["quality_state", "=", "none"]];
            this.state.extra.quality = await this.orm.searchCount("quality.check", domain);
            this.state.extra.qualityDomain = domain;
        } catch (e) {
            this.state.extra.quality = null;
        }
    }

    async loadMaintenance() {
        try {
            const domain = [["close_date", "=", false]];
            this.state.extra.maintenance = await this.orm.searchCount("maintenance.request", domain);
            this.state.extra.maintenanceDomain = domain;
        } catch (e) {
            this.state.extra.maintenance = null;
        }
    }

    async loadTrend() {
        const labels = [];
        const counts = [];
        for (let i = 6; i >= 0; i--) {
            const dayStart = new Date();
            dayStart.setHours(0, 0, 0, 0);
            dayStart.setDate(dayStart.getDate() - i);
            const dayEnd = new Date(dayStart);
            dayEnd.setDate(dayEnd.getDate() + 1);
            const count = await this.orm.searchCount("mrp.production", [
                ["state", "=", "done"],
                ["date_finished", ">=", this.toOdooDatetime(dayStart)],
                ["date_finished", "<", this.toOdooDatetime(dayEnd)],
            ]);
            labels.push(dayStart.toLocaleDateString(undefined, { weekday: "short" }));
            counts.push(count);
        }
        this.state.trend = { labels, counts };
        this.renderChart();
    }

    renderChart() {
        try {
            if (!this.chartCanvas.el || typeof Chart === "undefined") {
                return;
            }
            if (this.chart) {
                this.chart.data.labels = this.state.trend.labels;
                this.chart.data.datasets[0].data = this.state.trend.counts;
                this.chart.update();
                return;
            }
            this.chart = new Chart(this.chartCanvas.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: this.state.trend.labels,
                    datasets: [{
                        data: this.state.trend.counts,
                        backgroundColor: "#00b894",
                        borderRadius: 5,
                        maxBarThickness: 30,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false } },
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                    },
                },
            });
        } catch (e) {
            // Chart.js not available - fail silently, trend section stays hidden
        }
    }

    trendHeight(count) {
        const max = Math.max(...this.state.trend.counts, 1);
        return Math.max(8, Math.round((count / max) * 100));
    }

    setPeriod(period) {
        this.state.period = period;
        this.loadData();
    }

    // ---------- navigation ----------
    openWindow(model, domain, title, views) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: model,
            views: views || [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openMO(domain, title) {
        this.openWindow("mrp.production", domain, title, [[false, "list"], [false, "kanban"], [false, "form"]]);
    }

    openWO(domain, title) {
        this.openWindow("mrp.workorder", domain, title);
    }

    openWorkcenter(wc) {
        this.openWO([["workcenter_id", "=", wc.id], ["state", "not in", ["done", "cancel"]]], wc.name + " \u2014 job orders");
    }

    openRecord(rec) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            res_id: rec.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    createMO() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("manufacturing_dashboard_tag", ManufacturingDashboard);
