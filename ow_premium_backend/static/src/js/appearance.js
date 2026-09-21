/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { PALETTES, PRESETS } from "./theme_preferences";

export class AppearancePanel extends Component {
    static template = "ow_premium_backend.AppearancePanel";
    static props = {};
    setup() {
        this.appearance = useService("ow_appearance");
        this.state = useState(this.appearance.state);
        this.library = useState(this.appearance.library);
        this.editor = useState({ profileName: "", transfer: "", message: "", error: false, section: "design" });
        this.palettes = PALETTES;
        this.presets = PRESETS;
        this.preview = useState({ tab: "form", contact: "Alex Morgan", email: "alex@example.com", clicked: false });
    }
    set(name, value) {
        this.appearance.update({ [name]: value, ...(name === "palette" ? { customColors: false } : {}) });
    }
    saveProfile() {
        const error = this.appearance.saveProfile(this.editor.profileName);
        this.editor.error = Boolean(error);
        this.editor.message = error === "name" ? _t("Enter a name for your theme.") : error === "limit" ? _t("You can save up to eight themes. Remove one to make room.") : _t("Theme saved in this browser.");
        if (!error) this.editor.profileName = "";
    }
    loadProfile(profile) {
        this.appearance.update(profile.preferences);
        this.editor.error = false;
        this.editor.message = _t("Saved theme applied.");
    }
    exportTheme() {
        this.editor.transfer = this.appearance.exportTheme();
        this.editor.error = false;
        this.editor.message = _t("Your settings are ready below. Copy them to transfer your theme to another browser.");
    }
    importTheme() {
        try {
            this.appearance.importTheme(this.editor.transfer);
            this.editor.error = false;
            this.editor.message = _t("Theme imported. You can undo this change.");
        } catch {
            this.editor.error = true;
            this.editor.message = _t("Paste a valid Premium Backend theme export (up to 20 KB).");
        }
    }
    reset() { this.appearance.reset(); }
    applyPreset(preset) {
        const { palette, mode, surface, navbar, backdrop } = preset;
        this.appearance.update({ enabled: true, customColors: false, palette, mode, surface, navbar, backdrop });
    }
    isPreset(preset) {
        return !this.state.customColors && ["palette", "mode", "surface", "navbar", "backdrop"].every(key => this.state[key] === preset[key]);
    }
}
export class AppearanceAction extends Component {
    static template = "ow_premium_backend.AppearanceAction";
    static components = { AppearancePanel };
    static props = ["*"];
}
export class AppearanceDialog extends Component {
    static template = "ow_premium_backend.AppearanceDialog";
    static components = { Dialog, AppearancePanel };
    static props = { close: Function };
}
export class AppearanceSystray extends Component {
    static template = "ow_premium_backend.AppearanceSystray";
    static props = {};
    setup() {
        this.dialog = useService("dialog");
        this.appearance = useService("ow_appearance");
    }
    toggleMode() {
        const dark = document.documentElement.dataset.owMode === "dark";
        this.appearance.update({ mode: dark ? "light" : "dark" });
    }
    open() { this.dialog.add(AppearanceDialog, {}); }
    get title() { return _t("Customize appearance"); }
}
registry.category("actions").add("ow_premium_backend.appearance", AppearanceAction);
registry.category("systray").add("ow_premium_backend.appearance", { Component: AppearanceSystray }, { sequence: 5 });
