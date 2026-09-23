from odoo import api, models, tools


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    @tools.ormcache("self.env.uid", "debug")
    def _ow_hidden_menu_ids(self, debug=False):
        if self.env.su:
            return frozenset()
        profiles = self.env.user.sudo().ow_access_profile_ids.sudo().filtered(lambda profile: profile.active and profile.state == "applied")
        hidden = profiles.mapped("hidden_menu_ids")
        descendants = self.sudo().search([("id", "child_of", hidden.ids)]) if hidden else self.browse()
        return frozenset(descendants.ids)

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug=debug)
        return visible - self._ow_hidden_menu_ids(debug)
