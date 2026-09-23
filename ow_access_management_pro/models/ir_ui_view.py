from odoo import api, models


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if self.env.su or not view.model or view.model.startswith("ow.access."):
            return arch, view
        profiles = self.env.user.sudo().ow_access_profile_ids.sudo().filtered(lambda profile: profile.active and profile.state == "applied")
        policies = profiles.mapped("field_line_ids").filtered(lambda line: line.model_id.model == view.model)
        for policy in policies:
            for node in arch.xpath("//field[@name='%s']" % policy.field_id.name):
                node.set("invisible" if policy.policy == "hidden" else "readonly", "1")
        return arch, view
