def uninstall_hook(env):
    """Remove addon settings; Google-side consent must be revoked by the user."""
    env["ir.config_parameter"].sudo().search([("key", "in", [
        "ow_gmail_inbox.client_id", "ow_gmail_inbox.client_secret", "ow_gmail_inbox.base_url",
    ])]).unlink()
