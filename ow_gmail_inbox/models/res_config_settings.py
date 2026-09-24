from odoo import api, fields, models
from ..gmail_utils import redirect_uri


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ow_gmail_client_id = fields.Char(string="Google client ID", config_parameter="ow_gmail_inbox.client_id", groups="base.group_system")
    ow_gmail_client_secret = fields.Char(string="Google client secret", config_parameter="ow_gmail_inbox.client_secret", groups="base.group_system")
    ow_gmail_base_url = fields.Char(string="Public Odoo base URL", config_parameter="ow_gmail_inbox.base_url", groups="base.group_system",
                                   help="For example https://erp.example.com. Leave empty to use web.base.url.")
    ow_gmail_callback_url = fields.Char(string="Authorized redirect URI", compute="_compute_ow_gmail_callback", groups="base.group_system")

    @api.depends("ow_gmail_base_url")
    def _compute_ow_gmail_callback(self):
        for settings in self:
            base = settings.ow_gmail_base_url or self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            try:
                settings.ow_gmail_callback_url = redirect_uri(base)
            except ValueError:
                settings.ow_gmail_callback_url = "Set a valid HTTPS base URL above."
