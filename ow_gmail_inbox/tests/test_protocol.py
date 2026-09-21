"""Run directly: python3 tests/test_protocol.py. No Google account or Odoo DB."""
import importlib.util
import json
from email import policy
from email.parser import BytesParser
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

u = load("gmail_protocol", "gmail_utils.py")
client = load("gmail_http", "google_client.py")

class TestProtocol(unittest.TestCase):
    def test_oauth_user_database_expiration_and_replay_inputs(self):
        pending = u.oauth_pending(7, "db-a", "https://erp.example.com/ow_gmail/oauth/callback")
        self.assertTrue(u.valid_oauth_state(pending, pending["state"], 7, "db-a"))
        self.assertFalse(u.valid_oauth_state(pending, pending["state"], 8, "db-a"))
        self.assertFalse(u.valid_oauth_state(pending, pending["state"], 7, "db-b"))
        self.assertFalse(u.valid_oauth_state(pending, "wrong", 7, "db-a"))
        self.assertFalse(u.valid_oauth_state(pending, "☃", 7, "db-a"))
        self.assertFalse(u.valid_oauth_state(pending, pending["state"], 7, "db-a", pending["created"] + 601))
        self.assertFalse(u.valid_oauth_state(None, pending["state"], 7, "db-a"))
        self.assertEqual(u.challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_redirect_and_resource_validation(self):
        self.assertEqual(u.redirect_uri("https://erp.example.com/"), "https://erp.example.com/ow_gmail/oauth/callback")
        self.assertIn("localhost", u.redirect_uri("http://localhost:8069"))
        for value in ["http://example.com", "https://a@evil.test", "https://ok.test/?redirect=bad", "javascript:alert(1)"]:
            with self.assertRaises(ValueError): u.redirect_uri(value)
        for value in ["../profile", "x?alt=media", "a/b", None]:
            with self.assertRaises(ValueError): u.safe_id(value)

    def test_multipart_reader_plain_preference_and_attachment(self):
        message = {"id":"abc", "labelIds":["UNREAD","STARRED"], "payload":{
            "headers":[{"name":"Subject","value":"Hello"}], "parts":[
                {"mimeType":"text/plain", "body":{"data":u.b64encode(b'Plain body')}},
                {"mimeType":"text/html", "body":{"data":u.b64encode(b'<b>HTML body</b>')}},
                {"partId":"2", "filename":"a.pdf", "body":{"attachmentId":"attach","size":3}},
            ]}}
        result = u.message_data(message, full=True)
        self.assertEqual(result["body"], "Plain body")
        self.assertTrue(result["starred"])
        self.assertEqual(result["attachments"][0]["part_id"], "2")
        self.assertNotIn("attachmentId", json.dumps(result))
        self.assertEqual(u.find_attachment(message["payload"], "2")["filename"], "a.pdf")
        with self.assertRaises(ValueError): u.find_attachment(message["payload"], "99")

    def test_html_fallback_and_charset(self):
        msg={"id":"x", "payload":{"mimeType":"text/html", "body":{"data":u.b64encode(b'<html><head><style>BAD</style></head><body><script>BAD</script><p>Hello</p><img src="https://tracking.test/x"></body></html>')}}}
        text=u.message_data(msg,True)["body"]
        self.assertIn("Hello", text); self.assertNotIn("BAD", text); self.assertNotIn("tracking.test", text)
        msg["payload"]={"mimeType":"text/plain", "headers":[{"name":"Content-Type","value":"text/plain; charset=iso-8859-1"}],"body":{"data":u.b64encode('Café'.encode('latin1'))}}
        self.assertEqual(u.message_data(msg,True)["body"],"Café")

    def test_outgoing_message_headers_reply_and_files(self):
        raw=u.build_message("owner@example.com", {"to":"Alex <alex@example.com>","cc":"cc@example.com","bcc":"secret@example.com", "subject":"Re: Café", "body":"Hello ✓", "from":"attacker@example.com", "attachments":[{"name":"notes.txt","data":u.b64encode(b'notes')}]}, reply={"payload":{"headers":[{"name":"Message-ID","value":"<original@example.com>"}]}})
        msg=BytesParser(policy=policy.default).parsebytes(u.b64decode(raw))
        self.assertEqual(msg["From"],"owner@example.com")
        self.assertEqual(msg["Bcc"],"secret@example.com")
        self.assertEqual(msg["In-Reply-To"],"<original@example.com>")
        self.assertEqual(msg.get_body(preferencelist=('plain',)).get_content().strip(),"Hello ✓")
        self.assertEqual(list(msg.iter_attachments())[0].get_payload(decode=True),b'notes')

    def test_rejects_header_injection_and_attachment_abuse(self):
        base={"to":"a@example.com","subject":"Hi","body":"Hello"}
        for changes in [{"to":"a@example.com\r\nBcc: x@example.com"},{"subject":"Hi\nBcc: x@example.com"},{"to":"not-an-email"},{"attachments":[{}]*11},{"attachments":[{"name":"a.txt","data":"%%%"}]}]:
            with self.assertRaises(ValueError): u.build_message("owner@example.com",dict(base,**changes))
        with self.assertRaises(ValueError): u.b64decode(u.b64encode(b'12345'), limit=4)

    def test_transport_token_location_and_no_redirects(self):
        response=Mock(status_code=200,content=b'{}');response.json.return_value={"ok":True}
        with patch.object(client.requests,"request",return_value=response) as request:
            result=client.google_request("GET","https://gmail.googleapis.com/gmail/v1/users/me/profile",access_token="SECRET")
            self.assertTrue(result["ok"])
            self.assertFalse(request.call_args.kwargs["allow_redirects"])
            self.assertEqual(request.call_args.kwargs["headers"]["Authorization"],"Bearer SECRET")
            self.assertNotIn("SECRET",request.call_args.args[1])

    def test_ambiguous_send_not_retried_or_leaked(self):
        with patch.object(client.requests,"request",side_effect=client.requests.Timeout("secret=SECRET")) as request:
            with self.assertRaises(client.GoogleError) as raised:
                client.google_request("POST","https://gmail.googleapis.com/gmail/v1/users/me/messages/send",sending=True)
            self.assertEqual(request.call_count,1)
            self.assertIn("Check Sent",str(raised.exception));self.assertNotIn("SECRET",str(raised.exception))
        response=Mock(status_code=403,content=b'{"secret":"TOKEN"}')
        with patch.object(client.requests,"request",return_value=response):
            with self.assertRaises(client.GoogleError) as raised:client.google_request("GET","https://gmail.googleapis.com/")
            self.assertNotIn("TOKEN",str(raised.exception))

if __name__ == "__main__": unittest.main()
