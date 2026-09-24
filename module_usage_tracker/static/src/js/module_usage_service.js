/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

const HEARTBEAT_MS = 15000;
const MAX_CLIENT_DELTA_SECONDS = 60;
const EXCLUDED_XMLIDS = new Set([
    "module_usage_tracker.menu_module_usage_root",
    "module_usage_tracker.menu_module_usage_dashboard",
    "module_usage_tracker.menu_module_usage_logs",
]);
const EXCLUDED_NAMES = new Set(["Module Usage", "Module Usage Dashboard"]);

function isTrackerApp(app) {
    if (!app) {
        return false;
    }
    return EXCLUDED_XMLIDS.has(app.xmlid || "") || EXCLUDED_NAMES.has(app.name || "");
}

function newTabUuid() {
    if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function appPayload(app) {
    if (!app || isTrackerApp(app)) {
        return null;
    }
    return {
        module_name: app.name || "Unknown",
        module_xmlid: app.xmlid || "",
        menu_id: app.id || 0,
        action_id: app.actionID || app.actionPath || "",
    };
}

registry.category("services").add("module_usage_tracker", {
    dependencies: ["menu"],
    start(env, { menu }) {
        const tabUuid = newTabUuid();
        let currentApp = appPayload(menu.getCurrentApp());
        let lastTick = performance.now();
        let pendingSeconds = 0;

        const tick = () => {
            const now = performance.now();
            if (document.visibilityState === "visible" && currentApp) {
                const delta = Math.max(0, Math.round((now - lastTick) / 1000));
                pendingSeconds += Math.min(delta, MAX_CLIENT_DELTA_SECONDS);
            }
            lastTick = now;
        };

        const flush = async (payload = currentApp) => {
            tick();
            if (!payload || pendingSeconds <= 0) {
                pendingSeconds = 0;
                return;
            }
            const duration = pendingSeconds;
            pendingSeconds = 0;
            try {
                await rpc("/module_usage_tracker/ping", {
                    ...payload,
                    tab_uuid: tabUuid,
                    duration_seconds: duration,
                }, { silent: true });
            } catch {
                pendingSeconds += duration;
            }
        };

        const switchApp = async () => {
            const previousApp = currentApp;
            await flush(previousApp);
            currentApp = appPayload(menu.getCurrentApp());
            lastTick = performance.now();
        };

        env.bus.addEventListener("MENUS:APP-CHANGED", switchApp);
        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "hidden") {
                flush();
            } else {
                lastTick = performance.now();
            }
        });
        window.addEventListener("beforeunload", () => flush());
        window.setInterval(() => flush(), HEARTBEAT_MS);

        return { flush };
    },
});
