from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        """Inject the list of currently-active restricted model technical
        names into the session, so the JS field patch can check it
        synchronously on every Many2one render without an extra RPC.
        """
        result = super().session_info()
        restrictions = self.env['ow.link.restriction'].sudo().search([
            ('active', '=', True),
        ])
        result['ow_restricted_link_models'] = restrictions.mapped('model_name')
        return result
