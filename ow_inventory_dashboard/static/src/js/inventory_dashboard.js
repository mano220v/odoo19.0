/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";

export class OwInventoryDashboard extends Component {
    static template = "ow_inventory_dashboard.Dashboard";
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
                totalProducts: 0, inStock: 0, lowStock: 0, outOfStock: 0,
                totalTransfers: 0, readyTransfers: 0, lateTransfers: 0, backorders: 0,
            },
            extra: {
                incoming: null, incomingDomain: [],
                outgoing: null, outgoingDomain: [],
                internal: null, internalDomain: [],
                scrap: null, scrapDomain: [],
                onTimeRate: null, onTimeDomain: [],
                stockValue: null,
                reorderCount: null, reorderDomain: [],
            },
            locations: [],
            reorderList: [],
            trend: { labels: [], received: [], delivered: [] },
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

    // ---------- domains shared between counts (loadData) and card clicks ----------
    // Every KPI's count and its click-through use the exact same method, so the
    // number on a card and the list you land on after clicking it can never
    // drift apart, whatever period is selected.

    // Stock levels (not period-dependent - these are point-in-time on-hand figures)
    totalProductsDomain() {
        return [["type", "=", "consu"], ["active", "=", true]];
    }

    inStockDomain() {
        return [["type", "=", "consu"], ["active", "=", true], ["qty_available", ">", 0]];
    }

    lowStockDomain() {
        return [["qty_to_order", ">", 0]];
    }

    outOfStockDomain() {
        return [["type", "=", "consu"], ["active", "=", true], ["qty_available", "<=", 0]];
    }

    // Transfers (period-dependent where noted)
    totalTransfersDomain() {
        return [["state", "not in", ["done", "cancel"]], ...this.getPeriodDomainFor("scheduled_date")];
    }

    readyTransfersDomain() {
        return [["state", "=", "assigned"], ...this.getPeriodDomainFor("scheduled_date")];
    }

    lateTransfersDomain() {
        return [["state", "not in", ["done", "cancel"]], ["scheduled_date", "<", this.nowStr()]];
    }

    backordersDomain() {
        return [["backorder_id", "!=", false], ["state", "not in", ["done", "cancel"]]];
    }

    incomingDomain() {
        return [["picking_type_code", "=", "incoming"], ["state", "not in", ["done", "cancel"]], ...this.getPeriodDomainFor("scheduled_date")];
    }

    outgoingDomain() {
        return [["picking_type_code", "=", "outgoing"], ["state", "not in", ["done", "cancel"]], ...this.getPeriodDomainFor("scheduled_date")];
    }

    internalDomain() {
        return [["picking_type_code", "=", "internal"], ["state", "not in", ["done", "cancel"]], ...this.getPeriodDomainFor("scheduled_date")];
    }

    scrapDomain() {
        return [...this.getPeriodDomainFor("create_date")];
    }

    reorderDomain() {
        return [["qty_to_order", ">", 0]];
    }

    // ---------- data loading ----------
    async loadData() {
        this.state.loading = true;

        const [
            totalProducts, inStock, lowStock, outOfStock,
            totalTransfers, readyTransfers, lateTransfers, backorders,
        ] = await Promise.all([
            this.orm.searchCount("product.product", this.totalProductsDomain()),
            this.orm.searchCount("product.product", this.inStockDomain()),
            this.orm.searchCount("stock.warehouse.orderpoint", this.lowStockDomain()).catch(() => 0),
            this.orm.searchCount("product.product", this.outOfStockDomain()),
            this.orm.searchCount("stock.picking", this.totalTransfersDomain()),
            this.orm.searchCount("stock.picking", this.readyTransfersDomain()),
            this.orm.searchCount("stock.picking", this.lateTransfersDomain()),
            this.orm.searchCount("stock.picking", this.backordersDomain()),
        ]);

        this.state.kpi = { totalProducts, inStock, lowStock, outOfStock, totalTransfers, readyTransfers, lateTransfers, backorders };

        await Promise.all([
            this.loadIncomingOutgoingInternal(),
            this.loadScrap(),
            this.loadOnTimeRate(),
            this.loadStockValue(),
            this.loadReorderCount(),
        ]);

        const locGroups = await this.orm.call(
            "stock.quant",
            "read_group",
            [[["location_id.usage", "=", "internal"], ["quantity", "!=", 0]], ["quantity:sum"], ["location_id"]]
        );
        this.state.locations = locGroups
            .filter((g) => g.location_id)
            .map((g) => ({
                id: g.location_id[0],
                name: g.location_id[1],
                count: Math.round(g.quantity || 0),
            }))
            .sort((a, b) => b.count - a.count)
            .slice(0, 8);

        try {
            this.state.reorderList = await this.orm.searchRead(
                "stock.warehouse.orderpoint",
                this.reorderDomain(),
                ["product_id", "qty_to_order", "product_min_qty"],
                { order: "qty_to_order desc", limit: 6 }
            );
        } catch (e) {
            this.state.reorderList = [];
        }

        this.state.lastRefresh = new Date().toLocaleTimeString();
        this.state.loading = false;
    }

    async loadIncomingOutgoingInternal() {
        const [incoming, outgoing, internal] = await Promise.all([
            this.orm.searchCount("stock.picking", this.incomingDomain()),
            this.orm.searchCount("stock.picking", this.outgoingDomain()),
            this.orm.searchCount("stock.picking", this.internalDomain()),
        ]);
        this.state.extra.incoming = incoming;
        this.state.extra.incomingDomain = this.incomingDomain();
        this.state.extra.outgoing = outgoing;
        this.state.extra.outgoingDomain = this.outgoingDomain();
        this.state.extra.internal = internal;
        this.state.extra.internalDomain = this.internalDomain();
    }

    async loadScrap() {
        try {
            const domain = this.scrapDomain();
            this.state.extra.scrap = await this.orm.searchCount("stock.scrap", domain);
            this.state.extra.scrapDomain = domain;
        } catch (e) {
            this.state.extra.scrap = null;
        }
    }

    async loadOnTimeRate() {
        try {
            const domain = [["state", "=", "done"], ["picking_type_code", "=", "outgoing"], ...this.getPeriodDomainFor("date_done")];
            const records = await this.orm.searchRead("stock.picking", domain, ["scheduled_date", "date_done"], { limit: 500 });
            this.state.extra.onTimeDomain = domain;
            if (!records.length) {
                this.state.extra.onTimeRate = null;
                return;
            }
            let onTime = 0;
            for (const r of records) {
                if (!r.scheduled_date || (r.date_done && r.date_done <= r.scheduled_date)) {
                    onTime++;
                }
            }
            this.state.extra.onTimeRate = Math.round((onTime / records.length) * 100);
        } catch (e) {
            this.state.extra.onTimeRate = null;
        }
    }

    async loadStockValue() {
        try {
            const groups = await this.orm.call(
                "stock.quant",
                "read_group",
                [[["location_id.usage", "=", "internal"]], ["value:sum"], []]
            );
            const value = groups && groups[0] ? groups[0].value : null;
            this.state.extra.stockValue = typeof value === "number" ? Math.round(value) : null;
        } catch (e) {
            this.state.extra.stockValue = null;
        }
    }

    async loadReorderCount() {
        try {
            const domain = this.reorderDomain();
            this.state.extra.reorderCount = await this.orm.searchCount("stock.warehouse.orderpoint", domain);
            this.state.extra.reorderDomain = domain;
        } catch (e) {
            this.state.extra.reorderCount = null;
        }
    }

    async loadTrend() {
        const labels = [];
        const received = [];
        const delivered = [];
        for (let i = 6; i >= 0; i--) {
            const dayStart = new Date();
            dayStart.setHours(0, 0, 0, 0);
            dayStart.setDate(dayStart.getDate() - i);
            const dayEnd = new Date(dayStart);
            dayEnd.setDate(dayEnd.getDate() + 1);
            const startStr = this.toOdooDatetime(dayStart);
            const endStr = this.toOdooDatetime(dayEnd);

            const [inCount, outCount] = await Promise.all([
                this.orm.searchCount("stock.picking", [
                    ["state", "=", "done"], ["picking_type_code", "=", "incoming"],
                    ["date_done", ">=", startStr], ["date_done", "<", endStr],
                ]),
                this.orm.searchCount("stock.picking", [
                    ["state", "=", "done"], ["picking_type_code", "=", "outgoing"],
                    ["date_done", ">=", startStr], ["date_done", "<", endStr],
                ]),
            ]);
            labels.push(dayStart.toLocaleDateString(undefined, { weekday: "short" }));
            received.push(inCount);
            delivered.push(outCount);
        }
        this.state.trend = { labels, received, delivered };
        this.renderChart();
    }

    renderChart() {
        try {
            if (!this.chartCanvas.el || typeof Chart === "undefined") {
                return;
            }
            if (this.chart) {
                this.chart.data.labels = this.state.trend.labels;
                this.chart.data.datasets[0].data = this.state.trend.received;
                this.chart.data.datasets[1].data = this.state.trend.delivered;
                this.chart.update();
                return;
            }
            this.chart = new Chart(this.chartCanvas.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: this.state.trend.labels,
                    datasets: [
                        { label: "Received", data: this.state.trend.received, backgroundColor: "#0d9488", borderRadius: 5, maxBarThickness: 22 },
                        { label: "Delivered", data: this.state.trend.delivered, backgroundColor: "#6366f1", borderRadius: 5, maxBarThickness: 22 },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: true, position: "top", labels: { boxWidth: 10, font: { size: 11 } } } },
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

    maxTrendValue() {
        return Math.max(...this.state.trend.received, ...this.state.trend.delivered, 1);
    }

    trendHeight(count) {
        return Math.max(8, Math.round((count / this.maxTrendValue()) * 100));
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

    openProducts(domain, title) {
        this.openWindow("product.product", domain, title, [[false, "list"], [false, "kanban"], [false, "form"]]);
    }

    openPickings(domain, title) {
        this.openWindow("stock.picking", domain, title);
    }

    openOrderpoints(domain, title) {
        this.openWindow("stock.warehouse.orderpoint", domain, title);
    }

    openLocation(loc) {
        this.openWindow("stock.quant", [["location_id", "=", loc.id], ["quantity", "!=", 0]], loc.name + " \u2014 stock");
    }

    openReorderProduct(rec) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: rec.product_id[0],
            views: [[false, "form"]],
            target: "current",
        });
    }

    createTransfer() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "stock.picking",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("ow_inventory_dashboard_tag", OwInventoryDashboard);
