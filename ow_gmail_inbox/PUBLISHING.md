# Publishing notes

Technical name: `ow_gmail_inbox`. Version: `19.0.1.0.3`. Proposed price: USD 49.00. Manifest and static description follow the Odoo Wings conventions in the existing addons folder. Review commercial details before submission.

Version 19.0.1.0.3 gives opened messages a compact, bounded reading card. It prevents short plain-text messages from producing an oversized empty reader, keeps long messages scrollable, and supplies visible fallbacks for blank subjects, senders, recipients and message bodies.

Version 19.0.1.0.2 makes Google account selection explicit. The OAuth request omits `login_hint` and uses `prompt=select_account` as the only prompt. Reconnecting the same mailbox can preserve its existing encrypted refresh token when Google returns only a new access token. Odoo cannot inspect signed-in Google accounts directly.

This addon is a separate application and does not depend on `ow_premium_backend` or Odoo's SMTP/fetchmail Google connector. It uses the Gmail REST API with a Google Cloud OAuth client configured by the administrator.

The publisher/deployer must provide their own Google project, OAuth consent configuration, support and privacy-policy pages, and complete any Google verification applicable to that deployment. The README links the relevant primary Google documentation. No shared production client credentials are included.

Store imagery shows illustrative/mock mailbox data, never a real connected account. Replace or supplement it with installation screenshots before store submission if required. The code has not been published or uploaded, and no real email has been sent during development.

Static checks, protocol tests and isolated Owl browser checks do not certify successful installation, live OAuth or end-to-end Gmail interoperability. Odoo access-control tests are supplied for execution in a dedicated database.
