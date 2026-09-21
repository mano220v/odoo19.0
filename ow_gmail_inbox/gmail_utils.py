"""Gmail protocol utilities. No Odoo or network state; independently testable."""
import base64
import binascii
import hashlib
import hmac
import re
import secrets
import time
from email import policy
from email.message import EmailMessage
from email.utils import getaddresses
from html import unescape
from urllib.parse import urlparse

from lxml import html

SCOPE = "https://www.googleapis.com/auth/gmail.modify"
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_BODY_CHARS = 200000
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024


def b64encode(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def b64decode(value, limit=MAX_DOWNLOAD_BYTES):
    if not isinstance(value, str) or len(value) > (limit * 4 // 3) + 8:
        raise ValueError("Attachment or message data exceeds the supported size.")
    try:
        data = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid attachment encoding.") from exc
    if len(data) > limit:
        raise ValueError("Attachment exceeds the supported size.")
    return data


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,512}", value):
        raise ValueError("Invalid Gmail resource identifier.")
    return value


def redirect_uri(base_url):
    parsed = urlparse((base_url or "").strip())
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise ValueError("Set an HTTPS Odoo base URL (HTTP is allowed only on localhost).")
    if not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use an Odoo base URL without credentials, a query or a fragment.")
    return (base_url or "").strip().rstrip("/") + "/ow_gmail/oauth/callback"


def oauth_pending(uid, database, callback):
    verifier = secrets.token_urlsafe(48)
    return {"state": secrets.token_urlsafe(32), "verifier": verifier, "uid": uid,
            "database": database, "created": time.time(), "redirect_uri": callback}


def valid_oauth_state(pending, state, uid, database, now=None):
    return bool(isinstance(pending, dict) and isinstance(state, str) and
                isinstance(pending.get("state"), str) and
                hmac.compare_digest(pending["state"].encode(), state.encode()) and
                pending.get("uid") == uid and pending.get("database") == database and
                0 <= (time.time() if now is None else now) - pending.get("created", 0) <= 600)


def challenge(verifier):
    return b64encode(hashlib.sha256(verifier.encode("ascii")).digest())


def headers(payload):
    return {str(h.get("name", "")).lower(): str(h.get("value", ""))
            for h in payload.get("headers", [])}


def plain_html(value):
    try:
        tree = html.fromstring(value)
        for node in tree.xpath("//script|//style|//head|//iframe|//object"):
            node.drop_tree()
        for node in tree.xpath("//br|//p|//div|//li|//tr|//h1|//h2|//h3"):
            node.tail = "\n" + (node.tail or "")
        return tree.text_content().strip()
    except (ValueError, TypeError):
        return ""


def message_data(message, full=False):
    payload = message.get("payload", {})
    h = headers(payload)
    labels = message.get("labelIds", [])
    result = {"id": message["id"], "thread_id": message.get("threadId", ""),
              "subject": h.get("subject", "(No subject)"), "sender": h.get("from", ""),
              "to": h.get("to", ""), "cc": h.get("cc", ""),
              "date": h.get("date", ""), "snippet": unescape(message.get("snippet", "")),
              "unread": "UNREAD" in labels, "starred": "STARRED" in labels,
              "trashed": "TRASH" in labels, "labels": labels}
    if not full:
        return result
    plain, rich, attachments = [], [], []
    stack = [payload]
    total = 0
    while stack:
        part = stack.pop()
        stack.extend(reversed(part.get("parts", [])))
        body = part.get("body", {})
        filename = part.get("filename", "")
        if filename:
            attachments.append({"part_id": part.get("partId", ""), "name": filename[:255],
                                "size": body.get("size", 0), "mime": part.get("mimeType", "application/octet-stream")})
            continue
        kind = part.get("mimeType", "")
        if kind not in {"text/plain", "text/html"} or not body.get("data"):
            continue
        data = b64decode(body["data"], limit=2 * 1024 * 1024)
        total += len(data)
        if total > 2 * 1024 * 1024:
            break
        charset_match = re.search(r'charset=["\']?([^;"\' ]+)', headers(part).get("content-type", ""), re.I)
        charset = charset_match.group(1) if charset_match else "utf-8"
        try:
            decoded = data.decode(charset, errors="replace")
        except LookupError:
            decoded = data.decode("utf-8", errors="replace")
        (plain if kind == "text/plain" else rich).append(decoded)
    result.update({"body": ("\n\n".join(plain) if plain else plain_html("\n".join(rich)))[:MAX_BODY_CHARS],
                   "attachments": attachments,
                   "reply_to": h.get("reply-to", h.get("from", ""))})
    return result


def find_attachment(payload, part_id):
    stack = [payload]
    while stack:
        part = stack.pop()
        if part.get("partId", "") == part_id and part.get("filename"):
            return part
        stack.extend(part.get("parts", []))
    raise ValueError("Attachment not found on this message.")


def recipients(value, required=False):
    if not isinstance(value, str) or len(value) > 8000 or "\r" in value or "\n" in value:
        raise ValueError("Enter valid recipient addresses without line breaks.")
    if not value.strip():
        if required:
            raise ValueError("Enter at least one recipient.")
        return ""
    parsed = getaddresses([value.replace(";", ",")])
    if not parsed or len(parsed) > 100:
        raise ValueError("Enter between one and 100 recipients.")
    if any(not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", address) for _, address in parsed):
        raise ValueError("One or more recipient addresses are invalid.")
    # EmailMessage performs standards-compliant quoting and header encoding.
    return value.replace(";", ",")


def build_message(sender, values, reply=None):
    if not isinstance(values, dict):
        raise ValueError("Invalid message.")
    subject, body = values.get("subject", ""), values.get("body", "")
    if not isinstance(subject, str) or len(subject) > 998 or "\r" in subject or "\n" in subject:
        raise ValueError("Use a subject of at most 998 characters without line breaks.")
    if not isinstance(body, str) or len(body) > MAX_BODY_CHARS:
        raise ValueError("The message body is too large.")
    msg = EmailMessage(policy=policy.SMTP)
    msg["From"] = sender
    msg["To"] = recipients(values.get("to", ""), required=True)
    for header, key in [("Cc", "cc"), ("Bcc", "bcc")]:
        parsed = recipients(values.get(key, ""))
        if parsed:
            msg[header] = parsed
    msg["Subject"] = subject
    if reply:
        original = headers(reply.get("payload", {}))
        message_id = original.get("message-id", "")
        if message_id and not any(c in message_id for c in "\r\n"):
            msg["In-Reply-To"] = message_id[:998]
            references = original.get("references", "")
            if not any(c in references for c in "\r\n"):
                msg["References"] = (references + " " + message_id).strip()[-4000:]
    msg.set_content(body)
    attachments = values.get("attachments", [])
    if not isinstance(attachments, list) or len(attachments) > MAX_ATTACHMENTS:
        raise ValueError("Attach no more than ten files.")
    total = 0
    for item in attachments:
        if not isinstance(item, dict):
            raise ValueError("Invalid attachment.")
        name = item.get("name", "")
        if not isinstance(name, str) or not name.strip() or len(name) > 255 or any(c in name for c in "\r\n\x00"):
            raise ValueError("Invalid attachment filename.")
        data = b64decode(item.get("data", ""), MAX_ATTACHMENT_BYTES)
        total += len(data)
        if total > MAX_ATTACHMENT_BYTES:
            raise ValueError("Attachments must total 10 MB or less.")
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return b64encode(msg.as_bytes())
