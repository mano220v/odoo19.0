/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { Component, useState, onWillStart, onWillDestroy } from "@odoo/owl";

const PROVIDER_LABELS = {
    frankfurter: "Frankfurter.app (ECB data)",
    ecb: "European Central Bank",
    custom: "Custom API",
};

export class OwCurrencyDashboard extends Component {
    static template = "ow_currency_rate_updater.CurrencyDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            syncing: false,
            company: null,
            rows: [],
            search: "",
            sort: "code",
            sortDir: 1,
            view: "cards",
        });

        onWillStart(async () => {
            await this.loadData();
        });

        this._autoRefresh = setInterval(() => this.loadData(true), 60000);
        onWillDestroy(() => clearInterval(this._autoRefresh));
    }

    async loadData(silent = false) {
        if (!silent) this.state.loading = true;
        const companies = await this.orm.read(
            "res.company",
            [this.currentCompanyId()],
            [
                "name", "currency_id",
                "ow_currency_provider", "ow_currency_auto_update", "ow_currency_update_interval",
                "ow_currency_last_sync_date", "ow_currency_last_sync_state",
                "ow_currency_last_sync_message", "ow_currency_last_sync_count",
            ]
        );
        const company = companies[0];
        this.state.company = company;

        const currencies = await this.orm.searchRead(
            "res.currency",
            [["active", "=", true]],
            ["name", "symbol", "full_name"],
            { order: "name asc" }
        );
        const currencyIds = currencies.map((c) => c.id);
        const baseCurrencyId = company.currency_id[0];

        const rateHistory = await this.orm.searchRead(
            "res.currency.rate",
            [["company_id", "=", company.id], ["currency_id", "in", currencyIds]],
            ["currency_id", "name", "rate"],
            { order: "name asc", limit: 5000 }
        );

        const byCurrency = {};
        for (const rec of rateHistory) {
            const cid = rec.currency_id[0];
            if (!byCurrency[cid]) byCurrency[cid] = [];
            byCurrency[cid].push(rec);
        }

        const rows = [];
        for (const cur of currencies) {
            if (cur.id === baseCurrencyId) continue;
            const history = byCurrency[cur.id] || [];
            const last = history[history.length - 1];
            const prev = history[history.length - 2];
            const current = last ? last.rate : null;
            const previous = prev ? prev.rate : null;
            let changePct = null;
            if (current !== null && previous) {
                changePct = ((current - previous) / previous) * 100;
            }
            rows.push({
                id: cur.id,
                code: cur.name,
                symbol: cur.symbol,
                fullName: cur.full_name || cur.name,
                rate: current,
                changePct: changePct,
                trend: changePct === null ? "flat" : changePct > 0.0001 ? "up" : changePct < -0.0001 ? "down" : "flat",
                sparkline: this.buildSparkline(history.slice(-14).map((h) => h.rate)),
                lastDate: last ? last.name : null,
            });
        }
        this.state.rows = rows;
        this.state.loading = false;
    }

    buildSparkline(values) {
        if (!values || values.length < 2) return "";
        const w = 96, h = 28, pad = 2;
        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min || 1;
        const step = (w - pad * 2) / (values.length - 1);
        const points = values.map((v, i) => {
            const x = pad + i * step;
            const y = h - pad - ((v - min) / range) * (h - pad * 2);
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        });
        return points.join(" ");
    }

    currentCompanyId() {
        return this.state.company ? this.state.company.id : user.context.allowed_company_ids[0];
    }

    get providerLabel() {
        return this.state.company ? (PROVIDER_LABELS[this.state.company.ow_currency_provider] || this.state.company.ow_currency_provider) : "";
    }

    get baseCurrencyCode() {
        return this.state.company ? this.state.company.currency_id[1] : "";
    }

    get lastSyncLabel() {
        if (!this.state.company || !this.state.company.ow_currency_last_sync_date) return "Never synced";
        return this.timeAgo(this.state.company.ow_currency_last_sync_date);
    }

    timeAgo(dateStr) {
        const then = new Date(dateStr.replace(" ", "T") + "Z");
        const diffMs = Date.now() - then.getTime();
        const mins = Math.round(diffMs / 60000);
        if (mins < 1) return "just now";
        if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"} ago`;
        const hrs = Math.round(mins / 60);
        if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
        const days = Math.round(hrs / 24);
        return `${days} day${days === 1 ? "" : "s"} ago`;
    }

    get filteredRows() {
        let rows = this.state.rows;
        if (this.state.search) {
            const q = this.state.search.toLowerCase();
            rows = rows.filter((r) => r.code.toLowerCase().includes(q) || r.fullName.toLowerCase().includes(q));
        }
        const dir = this.state.sortDir;
        const key = this.state.sort;
        rows = [...rows].sort((a, b) => {
            let av = a[key], bv = b[key];
            if (av === null || av === undefined) av = key === "rate" || key === "changePct" ? -Infinity : "";
            if (bv === null || bv === undefined) bv = key === "rate" || key === "changePct" ? -Infinity : "";
            if (typeof av === "string") return av.localeCompare(bv) * dir;
            return (av - bv) * dir;
        });
        return rows;
    }

    setSort(key) {
        if (this.state.sort === key) {
            this.state.sortDir *= -1;
        } else {
            this.state.sort = key;
            this.state.sortDir = 1;
        }
    }

    setView(view) {
        this.state.view = view;
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
    }

    async syncNow() {
        this.state.syncing = true;
        try {
            const result = await this.orm.call("res.company", "action_sync_currency_rates_now", [[this.state.company.id]]);
            await this.loadData();
            if (result) {
                await this.action.doAction(result);
            }
        } catch (e) {
            this.notification.add(e.message?.data?.message || "Currency sync failed.", { type: "danger" });
        } finally {
            this.state.syncing = false;
        }
    }

    openSettings() {
        this.action.doAction("ow_currency_rate_updater.action_ow_currency_settings");
    }

    openCurrencies() {
        this.action.doAction("base.action_currency_form");
    }

    openLog() {
        this.action.doAction("ow_currency_rate_updater.action_currency_rate_sync_log");
    }
}

registry.category("actions").add("ow_currency_dashboard", OwCurrencyDashboard);
