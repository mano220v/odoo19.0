# Gmail Inbox — Odoo 19

Connect a personal Gmail or Google Workspace mailbox to Odoo through Google's OAuth authorization flow. Each internal Odoo user has one independent connection. Users sign in on Google's page, then return to their inbox inside Odoo. This addon does not change how users log in to Odoo.

## Installation

1. Extract `ow_gmail_inbox.zip` into your Odoo addons directory.
2. Add that directory to `addons_path`, restart Odoo, update the Apps list and install **Gmail Inbox | Google Mail Workspace**.
3. The addon depends on `web` and `base_setup`. Python packages `requests` and `cryptography` must be available in the Odoo environment (normally already present in an Odoo installation).
4. Complete the Google setup below. Open **Gmail Inbox → My Mailbox** and select **Connect with Google**.

No database or Google account was connected during development. Eight protocol tests and an isolated browser harness passed using fixtures/mocks. The browser check mounted the actual Owl component and exercised reading, escaped text, automatic read marking, replies, attachments, send-error preservation, pagination, search, responsive layouts and disconnect. Live OAuth and Odoo installation still need to be verified on your own instance.

## One-time Google setup

An Odoo administrator must configure a Google Cloud project. This cannot work with only a Gmail email address and password.

1. In Google Cloud, create/select your project and enable **Gmail API**.
2. Configure the Google Auth Platform/OAuth consent screen: app name, support contact, audience, required disclosures and authorized domains for your deployment.
3. Add the scope `https://www.googleapis.com/auth/gmail.modify`. It supports the inbox, sending and mailbox-label operations implemented here. The app does not request the full `mail.google.com` scope or permanent-delete permission.
4. For an external project in Testing, add the Gmail addresses that will connect to the test-user list. Google applies testing and token-lifetime limitations. Workspace internal apps and public external apps have different publication requirements.
5. Create an **OAuth client ID → Web application**. Use an OAuth client dedicated to this addon where possible.
6. In Odoo, open **Gmail Inbox → Configuration**. Enter the Google client ID, client secret and public Odoo base URL. Use HTTPS; HTTP is accepted only for localhost development.
7. Save the settings. Copy the displayed **Authorized redirect URI** into the Google OAuth client's **Authorized redirect URIs**. It must match exactly, including scheme, hostname, port and any deployment path. Example:

   `https://erp.example.com/ow_gmail/oauth/callback`

8. Sign in as the intended Odoo user, open **My Mailbox**, select **Choose a Google account**, choose one of the accounts already signed in to the browser (or select **Use another account**) and grant the requested mailbox access. Return through the displayed **Open Gmail Inbox** button.

The account list is displayed by Google on `accounts.google.com`, not read or rendered by Odoo. Browsers do not allow this addon to inspect signed-in Google accounts directly. The OAuth request deliberately omits `login_hint` and uses `prompt=select_account`, so Google asks which account to use. Google displays consent when permission has not already been granted. If the chooser contains only one account, select **Use another account** to add the test Gmail address.

Google classifies `gmail.modify` as a restricted scope. Public distribution can require restricted-scope verification and, depending on data handling and exemptions, a security assessment. Publishing the Odoo addon does not satisfy Google's verification requirements. Provide your own accurate public privacy policy and support details before deploying an external OAuth app.

Official references:
- [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- [Google OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies)

## Included features

- Per-user OAuth connection, offline refresh tokens and automatic access-token renewal.
- Inbox, Starred, Unread, Sent, All mail and Trash folders.
- Native Gmail search expressions (`from:`, `subject:`, `has:attachment`, etc.) and 15-message pagination.
- Read individual messages, automatically mark opened messages as read, toggle stars and unread status.
- Archive, move to Inbox, move to Trash and restore from Trash. There is no permanent-delete action.
- Compose plain-text messages with To, Cc and Bcc; reply with Gmail thread IDs and RFC reply headers.
- Attach up to ten files totaling 10 MiB per message. Download received attachments up to 25 MiB each.
- Responsive mailbox, list and reader layouts; a composer with send-in-progress protection and unsent-content confirmation.
- Failed sends retain the current compose fields. Ambiguous network failures explicitly ask users to check Sent before retrying; sends are not retried automatically.
- Local disconnect or explicit Google access revocation from the account menu.

## Data and privacy

Mailbox contents are requested on demand. This addon does not copy email messages or attachments into Odoo business records. Message text and selected attachment data pass through your Odoo server and remain in browser memory while the workspace is open. It does not load remote email images or execute HTML from messages; HTML-only messages are converted into text for display.

The database stores your connection email, owning Odoo user, connection date and encrypted OAuth tokens. Tokens live in a separate model without ordinary-user ACLs and are not returned to the frontend. Encryption uses a key derived from Odoo's `database.secret`; database/server administrators with access to that secret can decrypt tokens. This does not protect against a full database compromise. Protect database backups and the server. If `database.secret` changes, users need to reconnect. Google client credentials are stored in administrator-only Odoo system parameters.

Connections are scoped to the Odoo user, across companies available to that user. Company switching does not select a different mailbox. Unsent drafts remain in the currently open workspace only, are not saved in Gmail and are discarded when explicitly abandoned. The app prompts on normal navigation when content is unsent; browser termination can still lose it.

Disconnecting locally deletes that user's saved OAuth credentials from Odoo but does not revoke Google's authorization. **Revoke Google access** attempts revocation first and then deletes the connection. Revocation may affect other sessions using the same Google OAuth client. You can always remove the app in your Google Account's third-party connections page. Uninstalling removes this addon's OAuth configuration parameters and does not make a network revocation request; remove access in Google as needed.

## Scope and limits

Designed for Odoo 19 installations that accept custom Python addons. It is not an iframe of gmail.com and does not implement Google account login inside an embedded browser. It is an independent mailbox interface using the Gmail API.

One connected account per Odoo user. This first release does not include Gmail draft editing, HTML composition, remote-image rendering, complete threaded conversation grouping, alias sending, label creation, push notifications, background synchronization or automatic CRM/chatter linking. All mail excludes Spam and Trash under normal Gmail API semantics. Search stays scoped to the selected folder. The plain-text reader displays up to 200,000 characters per message.

Configure reverse-proxy request limits to accommodate base64-encoded uploads (at least 16 MiB for the supported 10 MiB attachment total). Requests use Google HTTPS endpoints with bounded network timeouts. Google quotas, Gmail sending limits, Workspace admin policies and OAuth consent restrictions still apply. The addon does not bypass these limits.

## Troubleshooting

- **Setup needed:** save the OAuth client ID and secret in Gmail Configuration.
- **redirect_uri_mismatch:** copy the exact callback URI shown in Odoo to the Google client; verify `web.base.url` or the configured public base URL and reverse-proxy HTTPS settings.
- **Access blocked / unverified app:** check the Google consent audience, test users, publication/verification status and Workspace admin policies.
- **Google denied request:** confirm Gmail API is enabled and mailbox permission was granted.
- **Expired authorization:** use **Reconnect Google**. Testing-mode or revoked refresh tokens can expire independently of this app.
- **Connection mismatch/expired request:** reconnect from the same browser and logged-in Odoo user. Authorization state expires after ten minutes and is consumed once.
- **Missing offline token:** remove the app from Google connections and authorize it again.
- **Uncertain send result:** check Gmail Sent before sending again.

## Validation

Run dependency-light tests without a database:

`python3 tests/test_protocol.py`

These cover OAuth user/database/session-state binding and expiration, PKCE, URL/resource checks, MIME parsing, text rendering, header injection prevention, recipient/attachment limits and transport error behavior. Google HTTP calls are mocked.

Odoo access-control integration tests are supplied in `tests/test_security.py`. Run them only on a dedicated test database using Odoo's `--test-enable --test-tags /ow_gmail_inbox` workflow. They cover user isolation, denied vault access, portal restrictions, encrypted token storage and forced sender ownership. These database tests were not executed during delivery.

Before production/store publication, verify installation and upgrades on Odoo 19, connect two test users, check cross-user isolation, exercise OAuth cancellation and refresh, send/reply to a test mailbox, confirm attachment downloads, and test disconnect/revocation. Any store preview captures are explicitly labeled as mock-data previews.

## Support and license

Odoo Wings — vsmanoj144@gmail.com. License: OPL-1. Proposed store price: USD 49.00; review price and publisher information before submitting. This is an independent integration and is not endorsed by Google. Gmail and Google are trademarks of Google LLC.
