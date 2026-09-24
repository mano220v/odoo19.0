/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";

const STORAGE_KEY_POSITION = "ow_sticky_notes.ball_position";
const STORAGE_KEY_OPEN = "ow_sticky_notes.panel_open";
const COLORS = ["yellow", "pink", "blue", "green", "purple", "orange"];

/**
 * Small debounce helper — kept local and dependency-free so this widget
 * never breaks due to a missing/renamed core hook in a future Odoo
 * version.
 */
function debounce(fn, delay) {
    let timer = null;
    const debounced = (...args) => {
        browser.clearTimeout(timer);
        timer = browser.setTimeout(() => fn(...args), delay);
    };
    debounced.cancel = () => browser.clearTimeout(timer);
    return debounced;
}

/**
 * Best-effort relative time formatting ("3 minutes ago"). Falls back to
 * a plain locale string if luxon isn't available for some reason.
 */
function formatRelative(dateStr) {
    if (!dateStr) {
        return "";
    }
    try {
        const then = new Date(dateStr.replace(" ", "T") + "Z");
        const now = new Date();
        const diffSec = Math.round((now - then) / 1000);
        const abs = Math.abs(diffSec);
        const units = [
            [31536000, "y"],
            [2592000, "mo"],
            [86400, "d"],
            [3600, "h"],
            [60, "m"],
        ];
        for (const [secs, suffix] of units) {
            if (abs >= secs) {
                const val = Math.round(abs / secs);
                return diffSec >= 0 ? `${val}${suffix} ${_t("ago")}` : `${_t("in")} ${val}${suffix}`;
            }
        }
        return _t("just now");
    } catch {
        return dateStr;
    }
}

export class StickyNotesWidget extends Component {
    static template = "ow_sticky_notes.StickyNotesWidget";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.hotkeyService = useService("hotkey");
        this.notification = useService("notification");

        this.ballRef = useRef("ball");
        this.colors = COLORS;

        this.state = useState({
            isOpen: false,
            loading: true,
            notes: [],
            filter: "all", // "all" | "context"
            ballX: null,
            ballY: null,
            dragging: false,
        });

        this._dragMoved = false;
        this._saveNote = debounce((note) => this._writeNote(note), 600);

        onWillStart(async () => {
            this.state.isOpen = browser.localStorage.getItem(STORAGE_KEY_OPEN) === "1";
            this._restoreBallPosition();
            await this._loadNotes();
        });

        onMounted(() => {
            this._hotkeyRemove = this.hotkeyService.add("alt+n", () => this.togglePanel(), {
                bypassEditableProtection: true,
            });
            this.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", this._updateContext.bind(this));
            this._updateContext();
        });

        onWillUnmount(() => {
            this._hotkeyRemove?.();
            this.env.bus.removeEventListener("ACTION_MANAGER:UI-UPDATED", this._updateContext.bind(this));
        });
    }

    // ---------------------------------------------------------------------
    // Data
    // ---------------------------------------------------------------------

    async _loadNotes() {
        this.state.loading = true;
        try {
            const records = await this.orm.searchRead(
                "ow.sticky.note",
                [],
                ["name", "content", "color", "sequence", "is_pinned", "res_model", "res_id", "res_name", "write_date"]
            );
            this.state.notes = records;
        } catch {
            this.notification.add(_t("Could not load your sticky notes."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async addNote() {
        const context = this._currentContext;
        const vals = {
            name: _t("Untitled"),
            content: "",
            color: COLORS[Math.floor(Math.random() * COLORS.length)],
        };
        if (this.state.filter === "context" && context.resModel && context.resId) {
            vals.res_model = context.resModel;
            vals.res_id = context.resId;
            vals.res_name = context.resName;
        }
        const [id] = await this.orm.create("ow.sticky.note", [vals]);
        const record = { id, is_pinned: false, sequence: 10, write_date: false, ...vals };
        this.state.notes.unshift(record);
    }

    onFieldInput(note, field, value) {
        note[field] = value;
        this._saveNote(note);
    }

    async _writeNote(note) {
        try {
            await this.orm.write("ow.sticky.note", [note.id], {
                name: note.name || _t("Untitled"),
                content: note.content || "",
            });
        } catch {
            this.notification.add(_t("A note failed to save. Your text is still on screen — try again."), {
                type: "warning",
            });
        }
    }

    async setColor(note, color) {
        note.color = color;
        await this.orm.write("ow.sticky.note", [note.id], { color });
    }

    async togglePin(note) {
        note.is_pinned = !note.is_pinned;
        await this.orm.write("ow.sticky.note", [note.id], { is_pinned: note.is_pinned });
        this._resortNotes();
    }

    async deleteNote(note) {
        this.state.notes = this.state.notes.filter((n) => n.id !== note.id);
        try {
            await this.orm.unlink("ow.sticky.note", [note.id]);
        } catch {
            this.notification.add(_t("Could not delete the note on the server."), { type: "danger" });
        }
    }

    async linkToCurrentRecord(note) {
        const context = this._currentContext;
        if (!context.resModel || !context.resId) {
            this.notification.add(_t("Open a record first to link a note to it."), { type: "warning" });
            return;
        }
        note.res_model = context.resModel;
        note.res_id = context.resId;
        note.res_name = context.resName;
        await this.orm.write("ow.sticky.note", [note.id], {
            res_model: context.resModel,
            res_id: context.resId,
            res_name: context.resName,
        });
    }

    _resortNotes() {
        this.state.notes.sort((a, b) => {
            if (!!b.is_pinned - !!a.is_pinned !== 0) {
                return !!b.is_pinned - !!a.is_pinned;
            }
            return (b.write_date || "").localeCompare(a.write_date || "");
        });
    }

    // ---------------------------------------------------------------------
    // Context (which record is currently open, if any)
    // ---------------------------------------------------------------------

    _updateContext() {
        this._currentContext = { resModel: false, resId: false, resName: false };
        try {
            const controller = this.actionService.currentController;
            const props = controller && controller.props;
            if (props && props.resModel && props.resId) {
                this._currentContext = {
                    resModel: props.resModel,
                    resId: props.resId,
                    resName: props.resId ? String(props.resId) : false,
                };
            }
        } catch {
            // Internals changed upstream — degrade gracefully, the widget
            // keeps working without record-linking.
        }
    }

    get visibleNotes() {
        if (this.state.filter === "context" && this._currentContext?.resModel) {
            return this.state.notes.filter(
                (n) => n.res_model === this._currentContext.resModel && n.res_id === this._currentContext.resId
            );
        }
        return this.state.notes;
    }

    get hasContext() {
        return !!(this._currentContext && this._currentContext.resModel && this._currentContext.resId);
    }

    formatDate(dateStr) {
        return formatRelative(dateStr);
    }

    // ---------------------------------------------------------------------
    // Panel open / close
    // ---------------------------------------------------------------------

    togglePanel() {
        this.state.isOpen = !this.state.isOpen;
        browser.localStorage.setItem(STORAGE_KEY_OPEN, this.state.isOpen ? "1" : "0");
    }

    closePanel() {
        this.state.isOpen = false;
        browser.localStorage.setItem(STORAGE_KEY_OPEN, "0");
    }

    // ---------------------------------------------------------------------
    // Draggable ball
    // ---------------------------------------------------------------------

    _restoreBallPosition() {
        const stored = browser.localStorage.getItem(STORAGE_KEY_POSITION);
        if (stored) {
            try {
                const { x, y } = JSON.parse(stored);
                this.state.ballX = x;
                this.state.ballY = y;
            } catch {
                // ignore corrupt value
            }
        }
    }

    onBallPointerDown(ev) {
        this._dragMoved = false;
        this._dragStart = { x: ev.clientX, y: ev.clientY };
        const rect = this.ballRef.el.getBoundingClientRect();
        this._ballStart = { x: rect.left, y: rect.top };
        this.state.dragging = true;

        const onMove = (moveEv) => {
            const dx = moveEv.clientX - this._dragStart.x;
            const dy = moveEv.clientY - this._dragStart.y;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                this._dragMoved = true;
            }
            const maxX = window.innerWidth - 56;
            const maxY = window.innerHeight - 56;
            this.state.ballX = Math.min(Math.max(0, this._ballStart.x + dx), maxX);
            this.state.ballY = Math.min(Math.max(0, this._ballStart.y + dy), maxY);
        };
        const onUp = () => {
            this.state.dragging = false;
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            if (this._dragMoved) {
                browser.localStorage.setItem(
                    STORAGE_KEY_POSITION,
                    JSON.stringify({ x: this.state.ballX, y: this.state.ballY })
                );
            } else {
                this.togglePanel();
            }
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
    }

    get ballStyle() {
        if (this.state.ballX === null || this.state.ballY === null) {
            return "";
        }
        return `left: ${this.state.ballX}px; top: ${this.state.ballY}px; right: auto; bottom: auto;`;
    }
}

registry.category("main_components").add("ow_sticky_notes.StickyNotesWidget", {
    Component: StickyNotesWidget,
});
