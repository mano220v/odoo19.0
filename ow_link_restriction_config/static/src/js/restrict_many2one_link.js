/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { session } from "@web/session";

/**
 * Model-scoped, view-scoped restriction of the Many2one "Internal link"
 * open-record navigation (the hover arrow in edit mode, and the clickable
 * readonly value, that jump to the linked record's form).
 *
 * - Restricted models come from `ow.link.restriction` (active=True),
 *   pushed into the session at login via ir.http.session_info().
 * - Only applied when the CURRENT record's model (the model the form/list
 *   is displaying, e.g. "hr.leave") is in that restricted list — this is
 *   NOT about the target/linked model, it's about which model's own view
 *   you're restricting.
 * - Only applied when env.config.viewType is "form" or "list".
 *   Kanban (and any other view type) is always left untouched.
 *
 * ODOO 19 NOTE
 * ------------
 * As of 19.0, Many2OneField no longer renders its own DOM: it just
 * computes `m2oProps` (via computeM2OProps) and passes them down to a
 * child <Many2One/> component (web/static/src/views/fields/many2one/many2one.js),
 * which owns the "hasExternalButton"/"onClick" logic that used to live
 * directly on Many2OneField in 17.0/18.0 — that getter and method no
 * longer exist on Many2OneField at all in 19.0.
 *
 * The readonly clickable value is now gated purely by the `canOpen` prop
 * (see web.Many2One template: an <a href=".."> is only rendered when
 * `canOpen` is true; otherwise a plain, non-clickable <span> is used),
 * and the same `canOpen` flag also controls the edit-mode external
 * "open record" button inside <Many2One/>. So instead of patching
 * hasExternalButton/onClick, we patch the `m2oProps` getter on
 * Many2OneField and force `canOpen: false` for restricted models —
 * this cleanly disables both the readonly link and the edit-mode
 * button in one place, without needing to touch the child component.
 */
const RESTRICTED_VIEW_TYPES = ["form", "list"];

patch(Many2OneField.prototype, {
    get isLinkRestricted() {
        const viewType = this.env.config && this.env.config.viewType;
        if (!RESTRICTED_VIEW_TYPES.includes(viewType)) {
            return false;
        }
        const resModel = this.props.record && this.props.record.resModel;
        const restrictedModels = session.ow_restricted_link_models || [];
        return restrictedModels.includes(resModel);
    },

    get m2oProps() {
        const props = super.m2oProps;
        if (this.isLinkRestricted) {
            return { ...props, canOpen: false };
        }
        return props;
    },
});
