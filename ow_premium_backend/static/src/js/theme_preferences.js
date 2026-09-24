/** @odoo-module **/
export const PALETTES = Object.freeze([
    { id: "indigo", name: "Indigo", color: "#4f46e5", strong: "#4338ca", soft: "#eef2ff", secondary: "#9333ea" },
    { id: "ocean", name: "Ocean", color: "#0369a1", strong: "#075985", soft: "#e0f2fe", secondary: "#0891b2" },
    { id: "emerald", name: "Emerald", color: "#047857", strong: "#065f46", soft: "#d1fae5", secondary: "#0f766e" },
    { id: "plum", name: "Plum", color: "#7e22ce", strong: "#6b21a8", soft: "#f3e8ff", secondary: "#be185d" },
    { id: "rose", name: "Rose", color: "#be185d", strong: "#9d174d", soft: "#fce7f3", secondary: "#7e22ce" },
    { id: "slate", name: "Slate", color: "#475569", strong: "#334155", soft: "#f1f5f9", secondary: "#1e293b" },
    { id: "royal", name: "Royal", color: "#4338ca", strong: "#3730a3", soft: "#e0e7ff", secondary: "#a21caf" },
    { id: "teal", name: "Teal", color: "#0f766e", strong: "#115e59", soft: "#ccfbf1", secondary: "#0369a1" },
    { id: "amber", name: "Amber", color: "#b45309", strong: "#92400e", soft: "#fef3c7", secondary: "#be123c" },
    { id: "ruby", name: "Ruby", color: "#b91c1c", strong: "#991b1b", soft: "#fee2e2", secondary: "#9d174d" },
    { id: "sapphire", name: "Sapphire", color: "#1d4ed8", strong: "#1e40af", soft: "#dbeafe", secondary: "#6d28d9" },
    { id: "bronze", name: "Bronze", color: "#854d0e", strong: "#713f12", soft: "#fef9c3", secondary: "#9a3412" },
]);
export const PRESETS = Object.freeze([
    { id: "aurora", name: "Aurora", description: "Violet gradients & glass", palette: "indigo", mode: "light", surface: "glass", navbar: "gradient", backdrop: "aurora" },
    { id: "midnight", name: "Midnight", description: "Deep blue & luminous accents", palette: "sapphire", mode: "dark", surface: "elevated", navbar: "midnight", backdrop: "mesh" },
    { id: "lagoon", name: "Lagoon", description: "Fresh teal & ocean tones", palette: "teal", mode: "light", surface: "glass", navbar: "gradient", backdrop: "mesh" },
    { id: "sunset", name: "Sunset", description: "Warm amber & ruby accents", palette: "amber", mode: "light", surface: "elevated", navbar: "gradient", backdrop: "aurora" },
    { id: "atelier", name: "Atelier", description: "Minimal slate & clean surfaces", palette: "slate", mode: "light", surface: "clean", navbar: "light", backdrop: "plain" },
]);
export const DEFAULTS = Object.freeze({
    enabled: true, mode: "light", palette: "indigo", density: "comfortable",
    corners: "rounded", motion: true,
    surface: "glass", navbar: "gradient", backdrop: "aurora",
    animation: "subtle", hoverLift: true, stripedRows: false, fieldGlow: true, fontScale: "standard",
    customColors: false, customPrimary: "#4f46e5", customSecondary: "#9333ea",
    fontFamily: "system", formWidth: "standard", inputStyle: "soft",
    tableStyle: "classic", cardAccent: "top", depth: 55, glow: 35,
    buttonShine: true, accentLine: true,
});
export function normalizePreferences(value) {
    const data = value && typeof value === "object" ? value : {};
    const choose = (key, values) => values.includes(data[key]) ? data[key] : DEFAULTS[key];
    const flag = key => typeof data[key] === "boolean" ? data[key] : DEFAULTS[key];
    const number = key => typeof data[key] === "number" && Number.isFinite(data[key]) ? Math.min(100, Math.max(0, Math.round(data[key]))) : DEFAULTS[key];
    const hex = key => typeof data[key] === "string" && /^#[0-9a-f]{6}$/i.test(data[key]) ? data[key].toLowerCase() : DEFAULTS[key];
    return {
        customColors: flag("customColors"), customPrimary: hex("customPrimary"), customSecondary: hex("customSecondary"),
        fontFamily: choose("fontFamily", ["system", "humanist", "geometric"]),
        formWidth: choose("formWidth", ["standard", "wide"]),
        inputStyle: choose("inputStyle", ["soft", "outlined", "minimal"]),
        tableStyle: choose("tableStyle", ["classic", "tinted"]),
        cardAccent: choose("cardAccent", ["top", "edge", "none"]),
        depth: number("depth"), glow: number("glow"),
        buttonShine: flag("buttonShine"), accentLine: flag("accentLine"),
        enabled: typeof data.enabled === "boolean" ? data.enabled : DEFAULTS.enabled,
        mode: ["light", "dark", "system"].includes(data.mode) ? data.mode : DEFAULTS.mode,
        palette: PALETTES.some(p => p.id === data.palette) ? data.palette : DEFAULTS.palette,
        density: ["comfortable", "compact"].includes(data.density) ? data.density : DEFAULTS.density,
        corners: ["rounded", "square"].includes(data.corners) ? data.corners : DEFAULTS.corners,
        motion: typeof data.motion === "boolean" ? data.motion : DEFAULTS.motion,
        surface: ["glass", "elevated", "clean"].includes(data.surface) ? data.surface : DEFAULTS.surface,
        navbar: ["gradient", "midnight", "light"].includes(data.navbar) ? data.navbar : DEFAULTS.navbar,
        backdrop: ["aurora", "mesh", "plain"].includes(data.backdrop) ? data.backdrop : DEFAULTS.backdrop,
        animation: ["subtle", "expressive"].includes(data.animation) ? data.animation : DEFAULTS.animation,
        hoverLift: typeof data.hoverLift === "boolean" ? data.hoverLift : DEFAULTS.hoverLift,
        stripedRows: typeof data.stripedRows === "boolean" ? data.stripedRows : DEFAULTS.stripedRows,
        fieldGlow: typeof data.fieldGlow === "boolean" ? data.fieldGlow : DEFAULTS.fieldGlow,
        fontScale: ["standard", "large"].includes(data.fontScale) ? data.fontScale : DEFAULTS.fontScale,
    };
}

// Bound external data before it reaches CSS variables or persistent storage.
export function normalizeProfiles(value) {
    if (!Array.isArray(value)) return [];
    const seen = new Set();
    return value.filter(item => item && typeof item === "object" && typeof item.id === "string" &&
        /^[a-z0-9-]{1,80}$/i.test(item.id) && !seen.has(item.id) && seen.add(item.id) &&
        typeof item.name === "string" && item.name.trim() && item.preferences && typeof item.preferences === "object")
        .slice(0, 8).map(item => ({ id: item.id, name: item.name.trim().slice(0, 40), preferences: normalizePreferences(item.preferences) }));
}
export function luminance(hex) {
    const rgb = hex.slice(1).match(/../g).map(v => parseInt(v, 16) / 255)
        .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
}
function mix(hex, amount, target = 0) {
    return "#" + hex.slice(1).match(/../g).map(v => Math.round(parseInt(v, 16) * (1 - amount) + target * amount).toString(16).padStart(2, "0")).join("");
}
export function readableAccent(hex) {
    let color = hex;
    for (let i = 0; i < 30 && 1.05 / (luminance(color) + 0.05) < 4.5; i++) color = mix(color, 0.08);
    return color;
}
export function resolvePalette(preferences) {
    const state = normalizePreferences(preferences);
    const source = PALETTES.find(p => p.id === state.palette);
    const color = readableAccent(state.customColors ? state.customPrimary : source.color);
    const secondary = readableAccent(state.customColors ? state.customSecondary : source.secondary);
    return { color, secondary, strong: mix(color, 0.15), soft: mix(color, 0.92, 255) };
}
export function parseTheme(text) {
    if (typeof text !== "string" || text.length > 20000) throw new Error("size");
    const data = JSON.parse(text);
    if (!data || data.format !== "ow-premium-backend" || data.version !== 1 ||
        !data.preferences || typeof data.preferences !== "object" || Array.isArray(data.preferences)) throw new Error("format");
    return normalizePreferences(data.preferences);
}
export function serializeTheme(preferences) {
    return JSON.stringify({ format: "ow-premium-backend", version: 1, preferences: normalizePreferences(preferences) }, null, 2);
}
