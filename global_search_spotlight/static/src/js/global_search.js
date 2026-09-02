/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { Component, useState, useRef, onMounted } from "@odoo/owl";

/**
 * NOTE on `useListener`
 * ----------------------------------------------------------------------
 * The legacy `useListener` hook (event-delegation helper from the OWL1 /
 * early-OWL2 compatibility layer) has been superseded in current Odoo
 * (17.0+) by plain declarative `t-on-*` directives directly in the QWeb
 * template - OWL2's template compiler handles delegation/binding natively
 * and more efficiently. That's what this module uses below
 * (`t-on-input`, `t-on-click`, `t-on-keydown`, ...); there is nothing to
 * import for it.
 *
 * NOTE on the Ctrl+K / Cmd+K shortcut
 * ----------------------------------------------------------------------
 * Odoo's own web client already binds "control+k" to its built-in Command
 * Palette (the app switcher). `useHotkey` below registers the *same*
 * combo for this module. In practice Odoo's hotkey service scopes
 * registrations to the current "active UI area" and the most recently
 * mounted/active owner generally wins, but if you find the two shortcuts
 * fighting each other in your instance, either:
 *   1) change the string below (e.g. "control+shift+k"), or
 *   2) unregister Odoo's default command palette hotkey from your own
 *      module by patching `@web/core/commands/command_palette_service`.
 */

/**
 * Minimal debounce helper: delays invoking `fn` until `delay` ms have
 * passed without it being called again. Used to avoid firing an RPC on
 * every single keystroke.
 */
function debounce(fn, delay) {
    let timeoutId = null;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
}

/**
 * SpotlightModal
 * ============================================================================
 * The centered search overlay. It only exists in the DOM while its parent
 * (SpotlightSystray) renders it via `t-if="state.isOpen"` - OWL mounts it
 * fresh every time it's opened and destroys it every time it's closed,
 * which conveniently gives us a clean slate (empty query/results) on
 * every open for free.
 */
export class SpotlightModal extends Component {
    static template = "global_search_spotlight.SpotlightModal";
    static props = {
        onClose: Function,
    };

    setup() {
        // --- Services -------------------------------------------------
        this.orm = useService("orm");           // modern RPC helper
        this.actionService = useService("action"); // for redirecting to a form view

        // --- Refs -------------------------------------------------------
        this.inputRef = useRef("spotlightInput");

        // --- Reactive state ----------------------------------------------
        this.state = useState({
            query: "",
            groupedResults: {},  // { Contacts: [...], Sales: [...], Products: [...] }
            flatResults: [],     // same records, flattened -> used for arrow-key nav
            activeIndex: -1,     // index into flatResults currently highlighted
            isLoading: false,
            hasSearched: false,
        });

        // Debounce the actual backend call by 300ms.
        this._debouncedSearch = debounce(this._search.bind(this), 300);

        // --- OWL lifecycle: onMounted -------------------------------------
        // Fires once, right after this component's first render has been
        // patched into the real DOM. This is the *correct* place to focus
        // the input - refs (`this.inputRef.el`) are only guaranteed to be
        // populated after mounting, never during setup()/willStart().
        onMounted(() => {
            this.inputRef.el?.focus();
        });
    }

    // ------------------------------------------------------------------
    // Event handlers (bound declaratively via t-on-* in the XML template)
    // ------------------------------------------------------------------

    /** Fired on every keystroke in the input. */
    onInput(ev) {
        const value = ev.target.value;
        this.state.query = value;
        this.state.activeIndex = -1;

        if (!value.trim()) {
            // Nothing typed (or just whitespace): clear results instantly,
            // don't bother calling the backend.
            this.state.groupedResults = {};
            this.state.flatResults = [];
            this.state.hasSearched = false;
            this.state.isLoading = false;
            return;
        }

        this.state.isLoading = true;
        this._debouncedSearch(value);
    }

    /** Keyboard navigation inside the modal: Esc / ArrowUp / ArrowDown / Enter. */
    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            this.props.onClose();
        } else if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this._moveActiveIndex(1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this._moveActiveIndex(-1);
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            const record = this.state.flatResults[this.state.activeIndex];
            if (record) {
                this.openRecord(record);
            }
        }
    }

    /** Clicking the dark backdrop (but not the modal card itself) closes it. */
    onBackdropClick(ev) {
        if (ev.target === ev.currentTarget) {
            this.props.onClose();
        }
    }

    /**
     * Redirects to the record's form view using the `action` service -
     * exactly how Odoo natively opens a record from, e.g., a many2one
     * autocomplete dropdown.
     */
    openRecord(record) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: record.model,
            res_id: record.id,
            views: [[false, "form"]],
            target: "current",
        });
        this.props.onClose();
    }

    // ------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------

    /** Performs the actual (debounced) RPC call to the backend. */
    async _search(query) {
        // Guard against race conditions: if the user kept typing after this
        // debounced call was scheduled, `this.state.query` has since moved
        // on - discard the now-stale response instead of overwriting newer
        // results with older ones.
        if (query !== this.state.query) {
            return;
        }
        try {
            const results = await this.orm.call(
                "global.search.spotlight",
                "search_all",
                [query],
                { limit: 5 },
            );
            if (query !== this.state.query) {
                return; // stale by the time the response came back
            }
            this._processResults(results);
        } catch (error) {
            console.error("Global Search Spotlight: search failed", error);
            this.state.groupedResults = {};
            this.state.flatResults = [];
        } finally {
            this.state.isLoading = false;
            this.state.hasSearched = true;
        }
    }

    /** Groups the flat backend result list by `category` for display. */
    _processResults(results) {
        const grouped = {};
        for (const item of results) {
            if (!grouped[item.category]) {
                grouped[item.category] = [];
            }
            grouped[item.category].push(item);
        }
        this.state.groupedResults = grouped;
        this.state.flatResults = results;
        this.state.activeIndex = results.length ? 0 : -1;
    }

    _moveActiveIndex(delta) {
        const len = this.state.flatResults.length;
        if (!len) {
            return;
        }
        this.state.activeIndex = (this.state.activeIndex + delta + len) % len;
    }

    /** Stable display order for the category groups. */
    get categoryOrder() {
        const priority = ["Contacts", "Sales", "Products"];
        return Object.keys(this.state.groupedResults).sort(
            (a, b) => priority.indexOf(a) - priority.indexOf(b)
        );
    }
}

/**
 * SpotlightSystray
 * ============================================================================
 * A small, always-mounted systray entry (top-right icon bar). It owns the
 * open/closed state of the modal and registers the global Ctrl+K / Cmd+K
 * hotkey for the lifetime of the web client session.
 */
export class SpotlightSystray extends Component {
    static template = "global_search_spotlight.SpotlightSystray";
    static components = { SpotlightModal };
    static props = {};

    setup() {
        this.state = useState({ isOpen: false });

        // `useHotkey` registers "control+k" for as long as this component
        // is mounted (i.e. the whole backend session, since systray items
        // are never destroyed). Odoo's hotkey service normalizes "control"
        // to Cmd on macOS automatically, so this one registration covers
        // both Ctrl+K (Win/Linux) and Cmd+K (Mac) - no platform branching
        // needed on our end.
        useHotkey("control+k", () => this.toggle(), {
            // Let the shortcut fire even while focus is inside another
            // input/textarea/contenteditable elsewhere on the page.
            bypassEditableProtection: true,
            global: true,
        });
    }

    toggle() {
        this.state.isOpen = !this.state.isOpen;
    }

    close() {
        this.state.isOpen = false;
    }
}

// Register the icon in the systray. `sequence` controls left-to-right
// ordering among systray items (lower numbers render further right).
registry.category("systray").add(
    "global_search_spotlight.systray",
    { Component: SpotlightSystray },
    { sequence: 1 },
);
