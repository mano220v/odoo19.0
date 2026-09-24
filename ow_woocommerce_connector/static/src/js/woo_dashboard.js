import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";

const EMPTY_DATA = {
    instances: 0,
    active_instances: 0,
    products: 0,
    customers: 0,
    orders: 0,
    failed_logs: 0,
    success_logs: 0,
    success_rate: 100,
    today_syncs: 0,
    last_sync: false,
    trend: [],
    operations: [],
    instance_data: [],
    logs: [],
};

class WooDashboard extends Component {
    static template = "ow_woocommerce_connector.Dashboard";
    static components = { Layout };
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.trendChartRef = useRef("trendChart");
        this.opsChartRef = useRef("opsChart");
        this.trendChart = null;
        this.opsChart = null;

        this.state = useState({
            loading: true,
            busyInstanceId: false,
            busyGlobal: false,
            logFilter: "all",
            showGuide: false,
            data: { ...EMPTY_DATA },
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
            this.state.showGuide = this.state.data.instances === 0;
        });

        useEffect(
            () => {
                if (!this.state.loading) {
                    this.renderCharts();
                }
            },
            () => [this.state.loading, this.state.data.trend, this.state.data.operations]
        );
    }

    get display() {
        return { controlPanel: {} };
    }

    get filteredLogs() {
        if (this.state.logFilter === "all") {
            return this.state.data.logs;
        }
        return this.state.data.logs.filter((log) => log.state === this.state.logFilter);
    }

    get hasFailures() {
        return this.state.data.failed_logs > 0;
    }

    async fetchData() {
        this.state.loading = true;
        try {
            this.state.data = await rpc("/woo_connector/dashboard/data", {});
        } finally {
            this.state.loading = false;
        }
    }

    setLogFilter(filter) {
        this.state.logFilter = filter;
    }

    toggleGuide() {
        this.state.showGuide = !this.state.showGuide;
    }

    formatDateTime(value) {
        if (!value) {
            return "Not synced yet";
        }
        const date = new Date(value.replace(" ", "T") + "Z");
        return date.toLocaleString();
    }

    healthLabel(health) {
        return {
            good: "Healthy",
            error: "Needs Attention",
            pending: "Not Synced Yet",
            inactive: "Inactive",
        }[health] || "Unknown";
    }

    async runGlobalAction(action) {
        this.state.busyGlobal = true;
        await this._runAction(action, false);
        this.state.busyGlobal = false;
    }

    async runInstanceAction(instanceId, action) {
        this.state.busyInstanceId = instanceId;
        await this._runAction(action, instanceId);
        this.state.busyInstanceId = false;
    }

    async _runAction(action, instanceId) {
        try {
            const result = await rpc("/woo_connector/dashboard/quick_action", {
                action,
                instance_id: instanceId || false,
            });
            if (result.success) {
                this.notification.add("Operation completed successfully.", { type: "success" });
            } else {
                this.notification.add(result.message || "Operation failed.", { type: "danger" });
            }
        } catch (error) {
            this.notification.add("Operation failed. Check the sync logs for details.", { type: "danger" });
        }
        await this.fetchData();
    }

    openInstance(instanceId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "woo.instance",
            res_id: instanceId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openNewInstance() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "woo.instance",
            views: [[false, "form"]],
            target: "current",
        });
    }

    renderCharts() {
        this.renderTrendChart();
        this.renderOpsChart();
    }

    renderTrendChart() {
        const canvas = this.trendChartRef.el;
        if (!canvas || typeof Chart === "undefined") {
            return;
        }
        const labels = this.state.data.trend.map((d) => d.label);
        const success = this.state.data.trend.map((d) => d.success);
        const failed = this.state.data.trend.map((d) => d.failed);
        if (this.trendChart) {
            this.trendChart.destroy();
        }
        this.trendChart = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    { label: "Success", data: success, backgroundColor: "#7f54b3", borderRadius: 4, maxBarThickness: 22 },
                    { label: "Failed", data: failed, backgroundColor: "#e35d6a", borderRadius: 4, maxBarThickness: 22 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
                },
                plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
            },
        });
    }

    renderOpsChart() {
        const canvas = this.opsChartRef.el;
        if (!canvas || typeof Chart === "undefined") {
            return;
        }
        if (this.opsChart) {
            this.opsChart.destroy();
            this.opsChart = null;
        }
        const labels = this.state.data.operations.map((o) => o.label);
        const values = this.state.data.operations.map((o) => o.value);
        if (!values.length) {
            return;
        }
        this.opsChart = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels,
                datasets: [
                    {
                        data: values,
                        backgroundColor: ["#7f54b3", "#9b7fc7", "#4f9da6", "#f0a85e", "#e35d6a", "#5b8def"],
                        borderWidth: 0,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "65%",
                plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
            },
        });
    }
}

registry.category("actions").add("ow_woocommerce_connector.dashboard", WooDashboard);
