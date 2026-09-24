/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export class OwAccountingPremiumDashboard extends Component {
    static template = "ow_accounting_premium_dashboard.Dashboard";
    static components = { Layout };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            period: "month",
            currency: "",
            companyName: "",
            error: false,
            lastUpdated: "",
            kpis: {
                income: null,
                expenses: null,
                net: null,
                receivables: null,
                payables: null,
                cash: null,
            },
            counts: { receivables: 0, payables: 0, overdue: 0, upcomingBills: 0 },
            overdueAmount: null,
            upcomingBillAmount: null,
            trend: [],
            overdueInvoices: [],
            dueBills: [],
            recentMoves: [],
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
        this.refreshTimer = setInterval(() => this.loadDashboard(), 120000);
        onWillUnmount(() => clearInterval(this.refreshTimer));
    }

    localDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    periodStart() {
        const now = new Date();
        if (this.state.period === "month") {
            return this.localDate(new Date(now.getFullYear(), now.getMonth(), 1));
        }
        if (this.state.period === "quarter") {
            const quarterMonth = Math.floor(now.getMonth() / 3) * 3;
            return this.localDate(new Date(now.getFullYear(), quarterMonth, 1));
        }
        if (this.state.period === "year") {
            return this.localDate(new Date(now.getFullYear(), 0, 1));
        }
        return null;
    }

    periodDomain(field = "invoice_date") {
        const start = this.periodStart();
        return start ? [[field, ">=", start]] : [];
    }

    moveDomain(types, extra = []) {
        return [["state", "=", "posted"], ["move_type", "in", types], ...this.companyDomain(), ...extra];
    }

    companyDomain(field = "company_id") {
        const companyId = this.companyId || user.activeCompany?.id || user.defaultCompany?.id;
        return companyId ? [[field, "=", companyId]] : [];
    }

    async aggregate(model, domain, field) {
        try {
            const groups = await this.orm.call(model, "read_group", [domain, [`${field}:sum`], []]);
            return Number(groups?.[0]?.[field] || 0);
        } catch (error) {
            return null;
        }
    }

    async count(model, domain) {
        try {
            return await this.orm.searchCount(model, domain);
        } catch (error) {
            return 0;
        }
    }

    async loadCompany() {
        try {
            const companyId = user.activeCompany?.id || user.defaultCompany?.id;
            this.companyId = companyId;
            const companies = await this.orm.searchRead(
                "res.company",
                companyId ? [["id", "=", companyId]] : [],
                ["name", "currency_id"],
                { limit: 1 }
            );
            const company = companies[0];
            this.companyId = company?.id || this.companyId;
            this.state.companyName = company?.name || "Accounting overview";
            if (company?.currency_id?.[0]) {
                const currencies = await this.orm.read("res.currency", [company.currency_id[0]], ["name"]);
                this.state.currency = currencies[0]?.name || "";
            }
        } catch (error) {
            this.state.companyName = "Accounting overview";
        }
    }

    async loadCashBalance() {
        try {
            const accounts = await this.orm.searchRead(
                "account.account",
                [["account_type", "=", "asset_cash"], ...this.companyDomain("company_ids")],
                ["id"],
                { limit: 1000 }
            );
            const ids = accounts.map((account) => account.id);
            if (!ids.length) {
                return 0;
            }
            return await this.aggregate(
                "account.move.line",
                [["account_id", "in", ids], ["parent_state", "=", "posted"], ...this.companyDomain()],
                "balance"
            );
        } catch (error) {
            return null;
        }
    }

    async loadTrend(requestId) {
        const now = new Date();
        const firstMonth = new Date(now.getFullYear(), now.getMonth() - 5, 1);
        const start = this.localDate(firstMonth);
        const domain = this.moveDomain(
            ["out_invoice", "out_refund", "in_invoice", "in_refund"],
            [["invoice_date", ">=", start]]
        );
        const monthIndex = new Map();
        const trend = Array.from({ length: 6 }, (_, index) => {
            const date = new Date(firstMonth.getFullYear(), firstMonth.getMonth() + index, 1);
            const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
            monthIndex.set(key, index);
            return { label: MONTHS[date.getMonth()], income: 0, expenses: 0 };
        });
        try {
            const groups = await this.orm.call("account.move", "read_group", [
                domain,
                ["invoice_date", "move_type", "amount_untaxed_signed:sum"],
                ["invoice_date:month", "move_type"],
            ], { lazy: false });
            for (const group of groups) {
                const dateKey = this.groupMonthKey(group);
                const index = monthIndex.get(dateKey);
                if (index === undefined) {
                    continue;
                }
                const amount = Number(group.amount_untaxed_signed || 0);
                if (["out_invoice", "out_refund"].includes(group.move_type)) {
                    trend[index].income += amount;
                } else {
                    trend[index].expenses -= amount;
                }
            }
            if (requestId === this._loadSequence) {
                this.state.trend = trend.map((item) => ({
                    ...item,
                    income: Math.max(0, item.income),
                    expenses: Math.max(0, item.expenses),
                }));
            }
        } catch (error) {
            if (requestId === this._loadSequence) {
                this.state.trend = trend;
            }
        }
    }

    groupMonthKey(group) {
        const range = group.__range?.["invoice_date:month"];
        const raw = range?.from || group["invoice_date:month"] || group.invoice_date;
        if (!raw) {
            return "";
        }
        const isoMatch = String(raw).match(/^(\d{4})-(\d{2})/);
        if (isoMatch) {
            return `${isoMatch[1]}-${isoMatch[2]}`;
        }
        const labelMatch = String(raw).match(/^([A-Za-z]+)\s+(\d{4})$/);
        if (labelMatch) {
            const month = new Date(`${labelMatch[1]} 1, ${labelMatch[2]}`).getMonth() + 1;
            return `${labelMatch[2]}-${String(month).padStart(2, "0")}`;
        }
        return "";
    }

    async loadDashboard() {
        const requestId = (this._loadSequence || 0) + 1;
        this._loadSequence = requestId;
        this.state.loading = true;
        this.state.error = false;
        try {
            await this.loadCompany();
            const period = this.periodDomain();
            const incomeDomain = this.moveDomain(["out_invoice", "out_refund"], period);
            const expenseDomain = this.moveDomain(["in_invoice", "in_refund"], period);
            const receivableDomain = this.moveDomain(
                ["out_invoice", "out_refund"],
                [["amount_residual", "!=", 0]]
            );
            const payableDomain = this.moveDomain(
                ["in_invoice", "in_refund"],
                [["amount_residual", "!=", 0]]
            );
            const overdueDomain = this.moveDomain(
                ["out_invoice", "out_refund"],
                [["amount_residual", "!=", 0], ["invoice_date_due", "<", this.localDate(new Date())]]
            );
            const today = new Date();
            const nextWeek = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7);
            const dueBillsDomain = this.moveDomain(
                ["in_invoice", "in_refund"],
                [["amount_residual", "!=", 0], ["invoice_date_due", ">=", this.localDate(today)], ["invoice_date_due", "<=", this.localDate(nextWeek)]]
            );
            const [income, expenses, receivablesRaw, payablesRaw, overdueRaw, upcomingRaw, receivables, payables, overdue, upcomingBills, cash] = await Promise.all([
                this.aggregate("account.move", incomeDomain, "amount_untaxed_signed"),
                this.aggregate("account.move", expenseDomain, "amount_untaxed_signed"),
                this.aggregate("account.move", receivableDomain, "amount_residual_signed"),
                this.aggregate("account.move", payableDomain, "amount_residual_signed"),
                this.aggregate("account.move", overdueDomain, "amount_residual_signed"),
                this.aggregate("account.move", dueBillsDomain, "amount_residual_signed"),
                this.count("account.move", receivableDomain),
                this.count("account.move", payableDomain),
                this.count("account.move", overdueDomain),
                this.count("account.move", dueBillsDomain),
                this.loadCashBalance(),
            ]);
            this.state.kpis = {
                income,
                expenses: expenses === null ? null : -expenses,
                net: income === null || expenses === null ? null : income + expenses,
                receivables: receivablesRaw,
                payables: payablesRaw === null ? null : -payablesRaw,
                cash,
            };
            this.state.counts = { receivables, payables, overdue, upcomingBills };
            this.state.overdueAmount = overdueRaw;
            this.state.upcomingBillAmount = upcomingRaw;

            const [, overdueRows, billRows, recentRows] = await Promise.all([
                this.loadTrend(requestId),
                this.orm.searchRead(
                    "account.move",
                    overdueDomain,
                    ["name", "partner_id", "invoice_date_due", "amount_residual_signed", "move_type"],
                    { order: "invoice_date_due asc", limit: 6 }
                ).catch(() => []),
                this.orm.searchRead(
                    "account.move",
                    dueBillsDomain,
                    ["name", "partner_id", "invoice_date_due", "amount_residual_signed", "move_type"],
                    { order: "invoice_date_due asc", limit: 5 }
                ).catch(() => []),
                this.orm.searchRead(
                    "account.move",
                    this.moveDomain(["out_invoice", "out_refund", "in_invoice", "in_refund"]),
                    ["name", "partner_id", "invoice_date", "amount_total_signed", "move_type", "payment_state"],
                    { order: "invoice_date desc, id desc", limit: 7 }
                ).catch(() => []),
            ]);
            if (requestId !== this._loadSequence) {
                return;
            }
            this.state.overdueInvoices = overdueRows;
            this.state.dueBills = billRows;
            this.state.recentMoves = recentRows;
            this.state.lastUpdated = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        } catch (error) {
            if (requestId === this._loadSequence) {
                this.state.error = true;
            }
        } finally {
            if (requestId === this._loadSequence) {
                this.state.loading = false;
            }
        }
    }

    async setPeriod(period) {
        this.state.period = period;
        await this.loadDashboard();
    }

    formatAmount(value, absolute = false) {
        if (value === null || value === undefined) {
            return "—";
        }
        const amount = absolute ? Math.abs(value) : value;
        try {
            return new Intl.NumberFormat(undefined, {
                style: this.state.currency ? "currency" : "decimal",
                currency: this.state.currency || undefined,
                maximumFractionDigits: 2,
            }).format(amount || 0);
        } catch (error) {
            return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(amount || 0);
        }
    }

    trendTotal(field) {
        return this.state.trend.reduce((total, month) => total + (month[field] || 0), 0);
    }

    barHeight(value) {
        const max = Math.max(1, ...this.state.trend.map((item) => Math.max(item.income, item.expenses)));
        return `${Math.max(value ? 5 : 0, Math.round((value / max) * 100))}%`;
    }

    moveTypeLabel(moveType) {
        return {
            out_invoice: "Customer invoice",
            out_refund: "Credit note",
            in_invoice: "Vendor bill",
            in_refund: "Vendor credit",
        }[moveType] || "Journal item";
    }

    paymentLabel(status) {
        return {
            paid: "Paid",
            not_paid: "Unpaid",
            partial: "Partial",
            in_payment: "In payment",
            reversed: "Reversed",
        }[status] || "Posted";
    }

    async openMoves(domain, name = "Journal Entries") {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "account.move",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openReceivables() {
        return this.openMoves(this.moveDomain(["out_invoice", "out_refund"], [["amount_residual", "!=", 0]]), "Open receivables");
    }

    openPayables() {
        return this.openMoves(this.moveDomain(["in_invoice", "in_refund"], [["amount_residual", "!=", 0]]), "Open payables");
    }

    openOverdue() {
        return this.openMoves(
            this.moveDomain(["out_invoice", "out_refund"], [["amount_residual", "!=", 0], ["invoice_date_due", "<", this.localDate(new Date())]]),
            "Overdue customer invoices"
        );
    }

    openCashAccounts() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Cash and Bank Journal Items",
            res_model: "account.move.line",
            views: [[false, "list"], [false, "form"]],
            domain: [["account_id.account_type", "=", "asset_cash"], ["parent_state", "=", "posted"], ...this.companyDomain()],
            target: "current",
        });
    }
}

registry.category("actions").add("ow_accounting_premium_dashboard", OwAccountingPremiumDashboard);
