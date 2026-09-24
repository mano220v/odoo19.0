import base64
import hashlib
import json
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from ..gmail_utils import (SCOPE, safe_id, redirect_uri, message_data, build_message,
                           find_attachment, b64decode, MAX_DOWNLOAD_BYTES)
from ..google_client import google_request, GoogleError

API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me/"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class GmailVault(models.Model):
    _name = "ow.gmail.vault"
    _description = "Private Gmail OAuth Credentials"
    # Intentionally no model ACL. Only checked, private server methods use sudo.
    account_id = fields.Many2one("ow.gmail.account", required=True, ondelete="cascade", index=True)
    credentials = fields.Text(required=True, copy=False)
    _unique_account = models.Constraint("UNIQUE(account_id)", "Only one credential set is allowed per account.")


class GmailAccount(models.Model):
    _name = "ow.gmail.account"
    _description = "Personal Gmail Connection"
    _rec_name = "email"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True, readonly=True)
    email = fields.Char(readonly=True)
    connected_at = fields.Datetime(readonly=True)
    _unique_user = models.Constraint("UNIQUE(user_id)", "Each Odoo user can connect one Gmail account.")

    def _require_internal(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("Gmail Inbox is available to internal users only."))

    def _configuration(self):
        self._require_internal()
        config = self.env["ir.config_parameter"].sudo()
        client_id = config.get_param("ow_gmail_inbox.client_id", "").strip()
        secret = config.get_param("ow_gmail_inbox.client_secret", "").strip()
        base = config.get_param("ow_gmail_inbox.base_url") or config.get_param("web.base.url", "")
        try:
            callback = redirect_uri(base)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        if not client_id or not secret:
            raise UserError(_("Ask your administrator to configure the Google OAuth client in Settings → Gmail Inbox."))
        return client_id, secret, callback

    def _cipher(self):
        secret = self.env["ir.config_parameter"].sudo().get_param("database.secret")
        if not secret:
            raise UserError(_("The database encryption secret is missing. Ask your administrator to restore database.secret."))
        key = base64.urlsafe_b64encode(hashlib.sha256(("ow_gmail_inbox:" + secret).encode()).digest())
        return Fernet(key)

    def _account(self, required=True):
        self._require_internal()
        account = self.sudo().search([("user_id", "=", self.env.uid)], limit=1)
        if required and not account:
            raise UserError(_("Connect your Google account first."))
        return account

    def _vault(self, account):
        return self.env["ow.gmail.vault"].sudo().search([("account_id", "=", account.id)], limit=1)

    def _read_credentials(self, account):
        vault = self._vault(account)
        if not vault:
            raise UserError(_("Reconnect your Google account to continue."))
        try:
            data = json.loads(self._cipher().decrypt(vault.credentials.encode()))
        except (InvalidToken, ValueError, TypeError):
            raise UserError(_("Saved credentials cannot be read. Please reconnect your Google account."))
        client_id, _, _ = self._configuration()
        if data.get("client_id") != client_id:
            raise UserError(_("The Google OAuth client changed. Please reconnect your account."))
        return data

    def _save_credentials(self, account, data):
        encrypted = self._cipher().encrypt(json.dumps(data).encode()).decode()
        vault = self._vault(account)
        if vault:
            vault.write({"credentials": encrypted})
        else:
            self.env["ow.gmail.vault"].sudo().create({"account_id": account.id, "credentials": encrypted})

    def _request(self, *args, **kwargs):
        try:
            return google_request(*args, **kwargs)
        except GoogleError as exc:
            raise UserError(str(exc)) from exc

    def _complete_oauth(self, code, pending):
        self._require_internal()
        client_id, secret, callback = self._configuration()
        if pending.get("redirect_uri") != callback:
            raise UserError(_("The callback URL changed during sign-in. Start connecting again."))
        tokens = self._request("POST", TOKEN_URL, data={
            "client_id": client_id, "client_secret": secret, "code": code,
            "grant_type": "authorization_code", "redirect_uri": callback,
            "code_verifier": pending["verifier"],
        })
        if SCOPE not in tokens.get("scope", "").split() or not tokens.get("access_token"):
            raise UserError(_("Gmail mailbox permission was not granted. Reconnect and allow the requested access."))
        profile = self._request("GET", API_ROOT + "profile", access_token=tokens["access_token"])
        email = profile.get("emailAddress", "")
        if not email or "@" not in email:
            raise UserError(_("Google did not return a Gmail mailbox for this account."))
        # Serialize connection replacement for this user; no duplicate account race.
        self.env.cr.execute("SELECT id FROM res_users WHERE id = %s FOR UPDATE", [self.env.uid])
        account = self._account(required=False)
        previous_email = account.email if account else ""
        values = {"email": email, "connected_at": fields.Datetime.now()}
        if account:
            account.write(values)
        else:
            account = self.sudo().create(dict(values, user_id=self.env.uid))
        refresh_token = tokens.get("refresh_token")
        if not refresh_token and previous_email == email and self._vault(account):
            # Google normally issues a refresh token on first authorization. On
            # reconnecting an already authorized mailbox it may issue only a new
            # access token; retain the server-side token for that same mailbox.
            refresh_token = self._read_credentials(account).get("refresh_token")
        if not refresh_token:
            raise UserError(_("Google did not issue an offline token. Remove this app from your Google account connections, then reconnect."))
        self._save_credentials(account, {
            "client_id": client_id, "access_token": tokens["access_token"],
            "refresh_token": refresh_token,
            "expires_at": fields.Datetime.to_string(fields.Datetime.now() + timedelta(seconds=int(tokens.get("expires_in", 3600)))),
        })

    def _access_token(self, account):
        data = self._read_credentials(account)
        expires = fields.Datetime.to_datetime(data.get("expires_at"))
        if expires and expires > fields.Datetime.now() + timedelta(seconds=90):
            return data["access_token"]
        client_id, secret, _ = self._configuration()
        tokens = self._request("POST", TOKEN_URL, data={
            "client_id": client_id, "client_secret": secret, "grant_type": "refresh_token",
            "refresh_token": data["refresh_token"],
        })
        if not tokens.get("access_token"):
            raise UserError(_("Reconnect your Google account to continue."))
        data.update({"access_token": tokens["access_token"],
                     "refresh_token": tokens.get("refresh_token", data["refresh_token"]),
                     "expires_at": fields.Datetime.to_string(fields.Datetime.now() + timedelta(seconds=int(tokens.get("expires_in", 3600))))})
        self._save_credentials(account, data)
        return data["access_token"]

    def _api(self, method, path, **kwargs):
        account = self._account()
        token = self._access_token(account)
        if kwargs.get("sending"):
            # Flush any refreshed credentials before the irreversible send so
            # ORM write conflicts surface before Google accepts the message.
            self.env.flush_all()
        return self._request(method, API_ROOT + path, access_token=token, **kwargs)

    def _checked_id(self, value):
        try:
            return safe_id(value)
        except ValueError as exc:
            raise UserError(str(exc)) from exc

    @api.model
    def connection_status(self):
        self._require_internal()
        account = self._account(required=False)
        config = self.env["ir.config_parameter"].sudo()
        configured = bool(config.get_param("ow_gmail_inbox.client_id") and config.get_param("ow_gmail_inbox.client_secret"))
        return {"connected": bool(account and self._vault(account)), "email": account.email or "",
                "configured": configured, "admin": self.env.user.has_group("base.group_system")}

    @api.model
    def list_messages(self, folder="INBOX", query="", page_token=""):
        self._require_internal()
        folders = {"INBOX", "SENT", "STARRED", "UNREAD", "TRASH", "ALL"}
        if folder not in folders or not isinstance(query, str) or len(query) > 1000:
            raise UserError(_("Choose a valid folder and a search of up to 1,000 characters."))
        if not isinstance(page_token, str) or len(page_token) > 2048:
            raise UserError(_("Invalid mailbox page."))
        params = {"maxResults": 15, "q": query}
        if folder != "ALL":
            params["labelIds"] = folder
        if folder == "TRASH":
            params["includeSpamTrash"] = "true"
        if page_token:
            params["pageToken"] = page_token
        token = self._access_token(self._account())
        listing = self._request("GET", API_ROOT + "messages", access_token=token, params=params)
        messages = []
        for item in listing.get("messages", [])[:15]:
            try:
                value = google_request("GET", API_ROOT + "messages/" + safe_id(item["id"]), access_token=token,
                                       params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]})
            except GoogleError as exc:
                if exc.status == 404:  # Message removed between list and metadata retrieval.
                    continue
                raise UserError(str(exc)) from exc
            messages.append(message_data(value))
        return {"messages": messages, "next_page": listing.get("nextPageToken", ""),
                "estimated_total": listing.get("resultSizeEstimate", 0)}

    @api.model
    def read_message(self, message_id):
        message_id = self._checked_id(message_id)
        value = self._api("GET", "messages/" + message_id, params={"format": "full"})
        # Google can store large text parts in the attachment endpoint, even
        # though they are the message body rather than a named user attachment.
        stack = [value.get("payload", {})]
        remaining = 2 * 1024 * 1024
        while stack:
            part = stack.pop()
            stack.extend(part.get("parts", []))
            body = part.get("body", {})
            if not part.get("filename") and part.get("mimeType") in {"text/plain", "text/html"} and body.get("attachmentId") and body.get("size", 0) <= remaining:
                extra = self._api("GET", "messages/" + message_id + "/attachments/" + self._checked_id(body["attachmentId"]))
                body["data"] = extra.get("data", "")
                remaining -= body.get("size", 0)
        try:
            return message_data(value, full=True)
        except ValueError as exc:
            raise UserError(str(exc)) from exc

    @api.model
    def modify_message(self, message_id, operation):
        message_id = self._checked_id(message_id)
        operations = {
            "read": ([], ["UNREAD"]), "unread": (["UNREAD"], []),
            "star": (["STARRED"], []), "unstar": ([], ["STARRED"]),
            "archive": ([], ["INBOX"]), "inbox": (["INBOX"], []),
        }
        if operation in {"trash", "untrash"}:
            self._api("POST", "messages/" + message_id + "/" + operation, json={})
        elif operation in operations:
            add, remove = operations[operation]
            self._api("POST", "messages/" + message_id + "/modify", json={"addLabelIds": add, "removeLabelIds": remove})
        else:
            raise UserError(_("Unsupported mailbox action."))
        return True

    @api.model
    def send_message(self, values):
        account = self._account()
        reply = None
        if isinstance(values, dict) and values.get("reply_id"):
            reply = self._api("GET", "messages/" + self._checked_id(values["reply_id"]), params={"format": "metadata", "metadataHeaders": ["Message-ID", "References", "Subject"]})
        try:
            raw = build_message(account.email, values, reply=reply)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        body = {"raw": raw}
        if reply:
            body["threadId"] = reply["threadId"]
        result = self._api("POST", "messages/send", json=body, sending=True)
        return {"id": result.get("id", ""), "sent": True}

    def _download_attachment(self, message_id, part_id):
        message_id = self._checked_id(message_id)
        if not isinstance(part_id, str) or len(part_id) > 100:
            raise UserError(_("Invalid attachment."))
        message = self._api("GET", "messages/" + message_id, params={"format": "full"})
        try:
            part = find_attachment(message.get("payload", {}), part_id)
            body = part.get("body", {})
            if body.get("size", 0) > MAX_DOWNLOAD_BYTES:
                raise ValueError("This attachment exceeds the 25 MB download limit. Open it in Gmail.")
            if body.get("attachmentId"):
                body = self._api("GET", "messages/" + message_id + "/attachments/" + self._checked_id(body["attachmentId"]))
            return part["filename"], b64decode(body.get("data", ""))
        except ValueError as exc:
            raise UserError(str(exc)) from exc

    @api.model
    def disconnect(self, revoke=False):
        account = self._account(required=False)
        if not account:
            return True
        if revoke:
            credentials = self._read_credentials(account)
            # A revocation failure leaves the local connection intact, allowing a retry.
            self._request("POST", "https://oauth2.googleapis.com/revoke", data={"token": credentials["refresh_token"]})
        account.unlink()
        return True
