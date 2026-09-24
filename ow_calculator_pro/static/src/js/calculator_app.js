/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { evaluateExpression, roundResult } from "./calculator_engine";
import { UNIT_CATEGORIES, convertUnit } from "./unit_data";

const TOOLS = [
    { id: "dashboard", label: "Dashboard", icon: "📊" },
    { id: "standard", label: "Standard", icon: "🧮" },
    { id: "scientific", label: "Scientific", icon: "🔬" },
    { id: "currency", label: "Currency", icon: "💱" },
    { id: "unit", label: "Unit Converter", icon: "📐" },
    { id: "loan", label: "Loan / EMI", icon: "🏦" },
    { id: "date", label: "Date Calculator", icon: "📅" },
    { id: "bmi", label: "BMI", icon: "⚖️" },
    { id: "discount", label: "Discount / Tax", icon: "🏷️" },
    { id: "history", label: "History", icon: "🕘" },
    { id: "favorites", label: "Favorites", icon: "⭐" },
];

const STANDARD_KEYS = [
    ["MC", "MR", "M+", "M-"],
    ["C", "⌫", "%", "/"],
    ["7", "8", "9", "*"],
    ["4", "5", "6", "-"],
    ["1", "2", "3", "+"],
    ["0", ".", "(", ")"],
];

const SCIENTIFIC_KEYS = [
    ["sin(", "cos(", "tan(", "π"],
    ["asin(", "acos(", "atan(", "e"],
    ["log(", "ln(", "sqrt(", "^"],
    ["(", ")", "!", "/"],
    ["7", "8", "9", "*"],
    ["4", "5", "6", "-"],
    ["1", "2", "3", "+"],
    ["0", ".", "C", "⌫"],
];

export class CalculatorApp extends Component {
    static template = "ow_calculator_pro.CalculatorApp";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.tools = TOOLS;
        this.standardKeys = STANDARD_KEYS;
        this.scientificKeys = SCIENTIFIC_KEYS;

        this.state = useState({
            activeTool: "dashboard",
            theme: "light",
            historyEnabled: true,
            decimalPrecision: 4,

            // standard / scientific
            expression: "",
            display: "0",
            memory: 0,
            errorMsg: "",

            // shared lists
            history: [],
            favorites: [],

            // currency
            currencies: [],
            currencyFromId: null,
            currencyToId: null,
            currencyAmount: 1,
            currencyResult: null,
            currencySource: null,
            // unit converter
            unitCategory: "length",
            unitFrom: "m",
            unitTo: "km",
            unitValue: 1,
            unitResult: null,

            // loan / EMI
            loanPrincipal: 100000,
            loanRate: 8.5,
            loanTenureYears: 5,
            loanEmi: null,
            loanTotalInterest: null,
            loanTotalPayment: null,
            loanSchedule: [],

            // date calculator
            dateFrom: "",
            dateTo: "",
            dateResult: null,

            // bmi
            bmiUnit: "metric",
            bmiHeight: 170,
            bmiWeight: 65,
            bmiValue: null,
            bmiCategory: "",

            // discount / tax
            discountPrice: 1000,
            discountPercent: 10,
            taxPercent: 18,
            discountResult: null,

            // dashboard
            dashboardTotals: { today: 0, week: 0, month: 0, total: 0 },
            dashboardByCategory: [],
            dashboardTrend: [],
        });

        onWillStart(async () => {
            await Promise.all([
                this.loadSettings(),
                this.loadFavorites(),
                this.loadHistory(),
                this.loadCurrencies(),
            ]);
            await this.loadDashboard();
        });

        this._onKeydown = (ev) => this.onKeydown(ev);
        onMounted(() => window.addEventListener("keydown", this._onKeydown));
        onWillUnmount(() => window.removeEventListener("keydown", this._onKeydown));
    }

    // ---------------------------------------------------------------------
    // Setup / data loading
    // ---------------------------------------------------------------------

    async loadSettings() {
        const params = await this.orm.call("ir.config_parameter", "get_param", [
            "ow_calculator_pro.decimal_precision",
            "4",
        ]);
        this.state.decimalPrecision = parseInt(params, 10) || 4;

        const historyEnabled = await this.orm.call("ir.config_parameter", "get_param", [
            "ow_calculator_pro.history_enabled",
            "True",
        ]);
        this.state.historyEnabled = historyEnabled === "True" || historyEnabled === "true";

        const storedTheme = window.localStorage.getItem("calculator_pro_theme");
        if (storedTheme) {
            this.state.theme = storedTheme;
        } else {
            const defaultTheme = await this.orm.call("ir.config_parameter", "get_param", [
                "ow_calculator_pro.default_theme",
                "light",
            ]);
            this.state.theme = defaultTheme || "light";
        }
    }

    async loadFavorites() {
        this.state.favorites = await this.orm.searchRead(
            "calculator.favorite",
            [],
            ["name", "category", "expression"],
            { order: "sequence, id" }
        );
    }

    async loadHistory() {
        this.state.history = await this.orm.searchRead(
            "calculator.history",
            [],
            ["category", "expression", "result", "create_date"],
            { order: "create_date desc", limit: 50 }
        );
    }

    async loadCurrencies() {
        const currencies = await this.orm.searchRead(
            "res.currency",
            [["active", "=", true]],
            ["name", "symbol"],
            { order: "name" }
        );
        this.state.currencies = currencies;
        const usd = currencies.find((c) => c.name === "USD") || currencies[0];
        const eur = currencies.find((c) => c.name === "EUR") || currencies[1] || currencies[0];
        if (usd) this.state.currencyFromId = usd.id;
        if (eur) this.state.currencyToId = eur.id;
    }

    async loadDashboard() {
        const now = new Date();
        const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const startOfWeek = new Date(startOfDay);
        startOfWeek.setDate(startOfWeek.getDate() - 6);
        const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

        const fmt = (d) => d.toISOString().slice(0, 19).replace("T", " ");

        const [today, week, month, total, byCategory] = await Promise.all([
            this.orm.searchCount("calculator.history", [["create_date", ">=", fmt(startOfDay)]]),
            this.orm.searchCount("calculator.history", [["create_date", ">=", fmt(startOfWeek)]]),
            this.orm.searchCount("calculator.history", [["create_date", ">=", fmt(startOfMonth)]]),
            this.orm.searchCount("calculator.history", []),
            this.orm.call("calculator.history", "read_group", [
                [],
                ["category"],
                ["category"],
            ]),
        ]);

        this.state.dashboardTotals = { today, week, month, total };
        this.state.dashboardByCategory = byCategory.map((g) => ({
            category: g.category,
            count: g.category_count,
        }));

        const trend = [];
        for (let i = 13; i >= 0; i--) {
            const dayStart = new Date(startOfDay);
            dayStart.setDate(dayStart.getDate() - i);
            const dayEnd = new Date(dayStart);
            dayEnd.setDate(dayEnd.getDate() + 1);
            const count = await this.orm.searchCount("calculator.history", [
                ["create_date", ">=", fmt(dayStart)],
                ["create_date", "<", fmt(dayEnd)],
            ]);
            trend.push({
                label: `${dayStart.getMonth() + 1}/${dayStart.getDate()}`,
                count,
            });
        }
        this.state.dashboardTrend = trend;
    }

    get maxTrendCount() {
        return Math.max(1, ...this.state.dashboardTrend.map((t) => t.count));
    }

    // ---------------------------------------------------------------------
    // Navigation / theme
    // ---------------------------------------------------------------------

    switchTool(toolId) {
        this.state.activeTool = toolId;
        this.state.errorMsg = "";
        if (toolId === "dashboard") {
            this.loadDashboard();
        }
    }

    toggleTheme() {
        this.state.theme = this.state.theme === "light" ? "dark" : "light";
        window.localStorage.setItem("calculator_pro_theme", this.state.theme);
    }

    // ---------------------------------------------------------------------
    // Standard / scientific calculator
    // ---------------------------------------------------------------------

    onKeydown(ev) {
        if (!["standard", "scientific"].includes(this.state.activeTool)) {
            return;
        }
        const target = ev.target;
        if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
            return;
        }
        if (/[0-9+\-*/.()%^]/.test(ev.key)) {
            this.pressKey(ev.key);
        } else if (ev.key === "Enter" || ev.key === "=") {
            ev.preventDefault();
            this.calculate();
        } else if (ev.key === "Backspace") {
            this.backspace();
        } else if (ev.key === "Escape") {
            this.clearDisplay();
        }
    }

    pressKey(key) {
        this.state.errorMsg = "";
        if (key === "C") {
            this.clearDisplay();
        } else if (key === "⌫") {
            this.backspace();
        } else if (key === "π") {
            this.state.expression += "pi";
        } else if (key === "M+") {
            this.state.memory += this._safeCurrentValue();
        } else if (key === "M-") {
            this.state.memory -= this._safeCurrentValue();
        } else if (key === "MR") {
            this.state.expression += String(this.state.memory);
        } else if (key === "MC") {
            this.state.memory = 0;
        } else if (key === "!") {
            this.state.expression += "!";
        } else {
            this.state.expression += key;
        }
        this.state.display = this.state.expression || "0";
    }

    _safeCurrentValue() {
        try {
            return evaluateExpression(this.state.expression);
        } catch {
            return 0;
        }
    }

    clearDisplay() {
        this.state.expression = "";
        this.state.display = "0";
        this.state.errorMsg = "";
    }

    backspace() {
        this.state.expression = this.state.expression.slice(0, -1);
        this.state.display = this.state.expression || "0";
    }

    async calculate() {
        try {
            const raw = evaluateExpression(this.state.expression);
            const result = roundResult(raw, this.state.decimalPrecision);
            this.state.display = String(result);
            await this.saveToHistory(this.state.activeTool, this.state.expression, result);
            this.state.expression = String(result);
        } catch (e) {
            this.state.errorMsg = e.message || "Invalid expression";
        }
    }

    async saveFavorite(category, expression) {
        if (!expression) {
            return;
        }
        await this.orm.create("calculator.favorite", [
            { name: expression, category, expression },
        ]);
        await this.loadFavorites();
        this.notification.add("Saved to favorites", { type: "success" });
    }

    useFavorite(fav) {
        this.state.activeTool = fav.category;
        if (["standard", "scientific"].includes(fav.category)) {
            this.state.expression = fav.expression;
            this.state.display = fav.expression;
        }
    }

    async deleteFavorite(id) {
        await this.orm.unlink("calculator.favorite", [id]);
        await this.loadFavorites();
    }

    async clearHistory() {
        await this.orm.call("calculator.history", "action_clear_my_history", []);
        await this.loadHistory();
        this.notification.add("History cleared", { type: "success" });
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(String(text));
        this.notification.add("Copied to clipboard", { type: "success" });
    }

    async saveToHistory(category, expression, result) {
        if (!this.state.historyEnabled || !expression) {
            return;
        }
        try {
            await this.orm.create("calculator.history", [
                { category, expression: String(expression), result: String(result) },
            ]);
            await this.loadHistory();
        } catch (e) {
            // Never block the UI if logging fails.
            console.error(e);
        }
    }

    // ---------------------------------------------------------------------
    // Currency converter
    // ---------------------------------------------------------------------

    async convertCurrency() {
        if (!this.state.currencyFromId || !this.state.currencyToId) {
            return;
        }
        try {
            const data = await this.orm.call("calculator.history", "get_currency_rate", [
                this.state.currencyFromId,
                this.state.currencyToId,
            ]);
            const result = roundResult(this.state.currencyAmount * data.rate, this.state.decimalPrecision);
            this.state.currencyResult = result;
            this.state.currencySource = data.source;
            const fromName = this.currencyName(this.state.currencyFromId);
            const toName = this.currencyName(this.state.currencyToId);
            await this.saveToHistory(
                "currency",
                `${this.state.currencyAmount} ${fromName} -> ${toName}`,
                `${result} ${toName}`
            );
        } catch (e) {
            this.state.errorMsg = e.message || "Could not fetch exchange rate";
        }
    }

    currencyName(id) {
        const currency = this.state.currencies.find((c) => c.id === id);
        return currency ? currency.name : "";
    }

    isOperatorKey(key) {
        return ["/", "*", "-", "+", "%", "^"].includes(key);
    }

    // ---------------------------------------------------------------------
    // Unit converter
    // ---------------------------------------------------------------------

    get unitOptions() {
        return Object.keys(UNIT_CATEGORIES[this.state.unitCategory].units);
    }

    onUnitCategoryChange(category) {
        this.state.unitCategory = category;
        const units = Object.keys(UNIT_CATEGORIES[category].units);
        this.state.unitFrom = units[0];
        this.state.unitTo = units[1] || units[0];
        this.state.unitResult = null;
    }

    async doUnitConvert() {
        const result = convertUnit(
            this.state.unitCategory,
            this.state.unitFrom,
            this.state.unitTo,
            parseFloat(this.state.unitValue) || 0
        );
        this.state.unitResult = roundResult(result, this.state.decimalPrecision);
        await this.saveToHistory(
            "unit",
            `${this.state.unitValue} ${this.state.unitFrom} -> ${this.state.unitTo}`,
            `${this.state.unitResult} ${this.state.unitTo}`
        );
    }

    // ---------------------------------------------------------------------
    // Loan / EMI calculator
    // ---------------------------------------------------------------------

    async calculateLoan() {
        const principal = parseFloat(this.state.loanPrincipal) || 0;
        const annualRate = parseFloat(this.state.loanRate) || 0;
        const years = parseFloat(this.state.loanTenureYears) || 0;
        const months = Math.round(years * 12);
        const monthlyRate = annualRate / 12 / 100;

        let emi;
        if (monthlyRate === 0) {
            emi = months > 0 ? principal / months : 0;
        } else {
            const factor = Math.pow(1 + monthlyRate, months);
            emi = (principal * monthlyRate * factor) / (factor - 1);
        }

        const totalPayment = emi * months;
        const totalInterest = totalPayment - principal;

        this.state.loanEmi = roundResult(emi, 2);
        this.state.loanTotalPayment = roundResult(totalPayment, 2);
        this.state.loanTotalInterest = roundResult(totalInterest, 2);

        const schedule = [];
        let balance = principal;
        for (let m = 1; m <= Math.min(months, 12); m++) {
            const interestPortion = balance * monthlyRate;
            const principalPortion = emi - interestPortion;
            balance = Math.max(0, balance - principalPortion);
            schedule.push({
                month: m,
                principalPortion: roundResult(principalPortion, 2),
                interestPortion: roundResult(interestPortion, 2),
                balance: roundResult(balance, 2),
            });
        }
        this.state.loanSchedule = schedule;

        await this.saveToHistory(
            "loan",
            `Loan ${principal} @ ${annualRate}% / ${years}y`,
            `EMI ${this.state.loanEmi}`
        );
    }

    // ---------------------------------------------------------------------
    // Date calculator
    // ---------------------------------------------------------------------

    async calculateDateDiff() {
        if (!this.state.dateFrom || !this.state.dateTo) {
            return;
        }
        const from = new Date(this.state.dateFrom);
        const to = new Date(this.state.dateTo);
        const diffMs = to - from;
        const totalDays = Math.round(Math.abs(diffMs) / (1000 * 60 * 60 * 24));

        let start = from < to ? from : to;
        let end = from < to ? to : from;
        let years = end.getFullYear() - start.getFullYear();
        let months = end.getMonth() - start.getMonth();
        let days = end.getDate() - start.getDate();
        if (days < 0) {
            months -= 1;
            const prevMonth = new Date(end.getFullYear(), end.getMonth(), 0);
            days += prevMonth.getDate();
        }
        if (months < 0) {
            years -= 1;
            months += 12;
        }

        this.state.dateResult = { totalDays, years, months, days };
        await this.saveToHistory(
            "date",
            `${this.state.dateFrom} -> ${this.state.dateTo}`,
            `${totalDays} days (${years}y ${months}m ${days}d)`
        );
    }

    // ---------------------------------------------------------------------
    // BMI calculator
    // ---------------------------------------------------------------------

    async calculateBmi() {
        const height = parseFloat(this.state.bmiHeight) || 0;
        const weight = parseFloat(this.state.bmiWeight) || 0;
        if (!height || !weight) {
            return;
        }
        let bmi;
        if (this.state.bmiUnit === "metric") {
            const heightM = height / 100;
            bmi = weight / (heightM * heightM);
        } else {
            bmi = (703 * weight) / (height * height);
        }
        bmi = roundResult(bmi, 1);
        let category;
        if (bmi < 18.5) category = "Underweight";
        else if (bmi < 25) category = "Normal";
        else if (bmi < 30) category = "Overweight";
        else category = "Obese";

        this.state.bmiValue = bmi;
        this.state.bmiCategory = category;
        await this.saveToHistory(
            "bmi",
            `${weight}${this.state.bmiUnit === "metric" ? "kg" : "lb"} / ${height}${
                this.state.bmiUnit === "metric" ? "cm" : "in"
            }`,
            `${bmi} (${category})`
        );
    }

    // ---------------------------------------------------------------------
    // Discount / tax calculator
    // ---------------------------------------------------------------------

    async calculateDiscount() {
        const price = parseFloat(this.state.discountPrice) || 0;
        const discountPct = parseFloat(this.state.discountPercent) || 0;
        const taxPct = parseFloat(this.state.taxPercent) || 0;

        const discountedPrice = price * (1 - discountPct / 100);
        const taxAmount = discountedPrice * (taxPct / 100);
        const finalPrice = discountedPrice + taxAmount;
        const youSave = price - discountedPrice;

        this.state.discountResult = {
            discountedPrice: roundResult(discountedPrice, 2),
            taxAmount: roundResult(taxAmount, 2),
            finalPrice: roundResult(finalPrice, 2),
            youSave: roundResult(youSave, 2),
        };

        await this.saveToHistory(
            "discount",
            `${price} - ${discountPct}% + tax ${taxPct}%`,
            `${this.state.discountResult.finalPrice}`
        );
    }
}

registry.category("actions").add("calculator_pro.dashboard", CalculatorApp);
