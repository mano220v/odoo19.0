"""Odoo integration tests: run in a separate test DB with --test-enable."""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestGmailIsolation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first = new_test_user(cls.env, login="ow_gmail_first", groups="base.group_user")
        cls.second = new_test_user(cls.env, login="ow_gmail_second", groups="base.group_user")
        cls.portal = new_test_user(cls.env, login="ow_gmail_portal", groups="base.group_portal")
        cls.account_a = cls.env["ow.gmail.account"].sudo().create({"user_id": cls.first.id, "email": "first@example.com"})
        cls.account_b = cls.env["ow.gmail.account"].sudo().create({"user_id": cls.second.id, "email": "second@example.com"})
        cls.vault = cls.env["ow.gmail.vault"].sudo().create({"account_id": cls.account_a.id, "credentials": "encrypted-placeholder"})
        config = cls.env["ir.config_parameter"].sudo()
        config.set_param("ow_gmail_inbox.client_id", "test.apps.googleusercontent.com")
        config.set_param("ow_gmail_inbox.client_secret", "test-secret")
        config.set_param("ow_gmail_inbox.base_url", "https://erp.example.com")

    def test_users_read_only_their_own_metadata(self):
        model = self.env["ow.gmail.account"].with_user(self.first)
        self.assertEqual(model.search([]), self.account_a)
        with self.assertRaises(AccessError): self.account_b.with_user(self.first).read(["email"])
        with self.assertRaises(AccessError): self.account_a.with_user(self.first).write({"email":"forged@example.com"})
        with self.assertRaises(AccessError): model.create({"user_id":self.first.id,"email":"forged@example.com"})

    def test_vault_is_not_rpc_readable(self):
        with self.assertRaises(AccessError): self.vault.with_user(self.first).read(["credentials"])
        with self.assertRaises(AccessError): self.env["ow.gmail.vault"].with_user(self.second).search([])

    def test_portal_cannot_use_public_methods(self):
        model = self.env["ow.gmail.account"].with_user(self.portal)
        for method, args in [("connection_status", []), ("list_messages", []), ("read_message", ["abc"]),
                             ("send_message", [{}]), ("disconnect", [])]:
            with self.assertRaises(AccessError): getattr(model, method)(*args)

    def test_disconnect_cannot_target_recordset_owner(self):
        self.account_b.with_user(self.first).disconnect()
        self.assertFalse(self.account_a.exists())
        self.assertTrue(self.account_b.exists())
        self.assertFalse(self.vault.exists())

    def test_tokens_are_encrypted_and_never_in_status(self):
        model = self.env["ow.gmail.account"].with_user(self.first)
        data = {"client_id":"test.apps.googleusercontent.com","access_token":"ACCESS_SECRET","refresh_token":"REFRESH_SECRET",
                "expires_at":fields.Datetime.to_string(fields.Datetime.now()+timedelta(hours=1))}
        model._save_credentials(self.account_a, data)
        self.assertNotIn("ACCESS_SECRET", self.vault.credentials)
        self.assertEqual(model._read_credentials(self.account_a), data)
        self.assertNotIn("SECRET", str(model.connection_status()))

    def test_sender_is_current_user_even_on_another_record(self):
        model = self.account_b.with_user(self.first)
        with patch.object(type(model), "_api", return_value={"id":"sent"}) as api:
            model.send_message({"to":"recipient@example.com","subject":"Test","body":"Content","from":"second@example.com"})
        from ..gmail_utils import b64decode
        raw = b64decode(api.call_args.kwargs["json"]["raw"]).decode()
        self.assertIn("From: first@example.com",raw)
        self.assertNotIn("From: second@example.com",raw)
