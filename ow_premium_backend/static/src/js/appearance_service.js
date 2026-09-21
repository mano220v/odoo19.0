/** @odoo-module **/
import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";
import { DEFAULTS, normalizePreferences, normalizeProfiles, resolvePalette, parseTheme, serializeTheme } from "./theme_preferences";

registry.category("services").add("ow_appearance", {
    start() {
        const key = `ow_premium_backend:v1:${session.db || "default"}:${session.uid || 0}`;
        const profilesKey = `${key}:profiles`;
        function read(name) {
            try { return JSON.parse(browser.localStorage.getItem(name) || "null"); } catch { return null; }
        }
        const state = reactive(normalizePreferences(read(key)));
        const library = reactive({ profiles: normalizeProfiles(read(profilesKey)), undoCount: 0, persistent: true });
        const history = [];
        const media = window.matchMedia("(prefers-color-scheme: dark)");
        function persist(name, data) {
            try { browser.localStorage.setItem(name, JSON.stringify(data)); }
            catch { library.persistent = false; }
        }
        function apply() {
            const root = document.documentElement;
            const palette = resolvePalette(state);
            root.classList.toggle("ow-premium", state.enabled);
            root.dataset.owMode = state.mode === "system" ? (media.matches ? "dark" : "light") : state.mode;
            for (const name of ["density", "corners", "motion", "surface", "navbar", "backdrop", "animation", "hoverLift", "stripedRows", "fieldGlow", "fontScale", "fontFamily", "formWidth", "inputStyle", "tableStyle", "cardAccent", "buttonShine", "accentLine"]) {
                root.dataset[`ow${name[0].toUpperCase()}${name.slice(1)}`] = String(state[name]);
            }
            for (const [name, value] of Object.entries({
                "accent": palette.color, "accent-strong": palette.strong,
                "palette-soft": palette.soft, "secondary": palette.secondary,
                "depth-alpha": (state.depth * 0.0025).toFixed(3),
                "glow-alpha": (state.glow * 0.004).toFixed(3),
                "focus-color": `color-mix(in srgb, ${palette.color} ${state.glow * 0.4}%, transparent)`,
            })) root.style.setProperty(`--ow-${name}`, value);
        }
        function update(changes) {
            const next = normalizePreferences({ ...state, ...changes });
            if (JSON.stringify(next) === JSON.stringify(state)) return;
            history.push({ ...state });
            if (history.length > 20) history.shift();
            library.undoCount = history.length;
            Object.assign(state, next);
            apply();
            persist(key, state);
        }
        function undo() {
            if (!history.length) return;
            Object.assign(state, history.pop());
            library.undoCount = history.length;
            apply();
            persist(key, state);
        }
        function saveProfile(name) {
            const clean = typeof name === "string" ? name.trim().slice(0, 40) : "";
            if (!clean) return "name";
            if (library.profiles.length >= 8) return "limit";
            library.profiles = [...library.profiles, {
                id: (globalThis.crypto?.randomUUID?.() || `theme-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`), name: clean, preferences: normalizePreferences(state),
            }];
            persist(profilesKey, library.profiles);
            return null;
        }
        function removeProfile(id) {
            library.profiles = library.profiles.filter(profile => profile.id !== id);
            persist(profilesKey, library.profiles);
        }
        media.addEventListener("change", apply);
        browser.addEventListener("storage", (event) => {
            if (event.key === profilesKey || event.key === null) library.profiles = normalizeProfiles(read(profilesKey));
            if (event.key === key || event.key === null) {
                Object.assign(state, normalizePreferences(read(key)));
                history.length = 0;
                library.undoCount = 0;
                apply();
            }
        });
        apply();
        return {
            state, library, update, undo, saveProfile, removeProfile,
            reset: () => update(DEFAULTS),
            exportTheme: () => serializeTheme(state),
            importTheme: text => update(parseTheme(text)),
        };
    },
});
