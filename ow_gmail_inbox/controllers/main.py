from urllib.parse import urlencode

from odoo import http, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request, content_disposition

from ..gmail_utils import SCOPE, oauth_pending, valid_oauth_state, challenge


class GmailController(http.Controller):
    def _result(self, message, success=False, status=200):
        action = request.env.ref("ow_gmail_inbox.action_gmail_inbox").id
        response = request.render("ow_gmail_inbox.oauth_result", {
            "message": message, "success": success, "app_url": "/odoo/action-%s" % action,
        }, status=status)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @http.route("/ow_gmail/connect", type="http", auth="user", methods=["GET"])
    def connect(self, **kwargs):
        service = request.env["ow.gmail.account"]
        try:
            client_id, _, callback = service._configuration()
        except (UserError, AccessError) as exc:
            return self._result(str(exc), status=400)
        pending = oauth_pending(request.env.uid, request.env.cr.dbname, callback)
        request.session["ow_gmail_oauth"] = pending
        params = {"client_id": client_id, "redirect_uri": callback, "response_type": "code",
                  # Google owns the account chooser. Keeping login_hint absent and
                  # using select_account as the only prompt asks Google to display
                  # the chooser instead of continuing with its default session.
                  "scope": SCOPE, "access_type": "offline", "prompt": "select_account",
                  "state": pending["state"], "code_challenge": challenge(pending["verifier"]),
                  "code_challenge_method": "S256"}
        response = request.redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), local=False)
        response.headers["Cache-Control"] = "no-store"
        return response

    @http.route("/ow_gmail/oauth/callback", type="http", auth="user", methods=["GET"])
    def callback(self, code=None, state=None, error=None, **kwargs):
        pending = request.session.pop("ow_gmail_oauth", None)
        if not valid_oauth_state(pending, state, request.env.uid, request.env.cr.dbname):
            return self._result(_("The sign-in request is expired or does not match this session. Open Gmail Inbox and connect again."), status=400)
        if error:
            return self._result(_("Google sign-in was cancelled or permission was not granted. You can connect again when ready."), status=400)
        if not isinstance(code, str) or not code or len(code) > 4096:
            return self._result(_("Google did not return a valid authorization code."), status=400)
        try:
            # Keep partial account changes out of the transaction when a handled error occurs.
            with request.env.cr.savepoint():
                request.env["ow.gmail.account"]._complete_oauth(code, pending)
        except (UserError, AccessError) as exc:
            return self._result(str(exc), status=400)
        return self._result(_("Your Gmail account is connected. Open your inbox to start reading and composing."), success=True)

    @http.route("/ow_gmail/attachment/<string:message_id>", type="http", auth="user", methods=["GET"])
    def attachment(self, message_id, part_id="", **kwargs):
        try:
            name, content = request.env["ow.gmail.account"]._download_attachment(message_id, part_id)
        except (UserError, AccessError) as exc:
            return self._result(str(exc), status=400)
        name = name.replace("\r", "").replace("\n", "").replace("\x00", "")
        return request.make_response(content, headers=[
            ("Content-Type", "application/octet-stream"),
            ("Content-Disposition", content_disposition(name)),
            ("Content-Length", str(len(content))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Content-Security-Policy", "default-src 'none'; sandbox"),
        ])
