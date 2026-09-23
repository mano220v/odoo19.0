from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    ow_access_profile_ids = fields.Many2many("ow.access.profile", "ow_access_profile_user_rel", "user_id", "profile_id", string="Access Profiles", readonly=True)
