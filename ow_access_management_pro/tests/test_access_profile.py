from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAccessProfile(TransactionCase):
    def test_apply_creates_native_security(self):
        user = self.env["res.users"].create({
            "name": "Profile Test User",
            "login": "profile-test@example.invalid",
        })
        profile = self.env["ow.access.profile"].create({
            "name": "Test Sales Reader",
            "user_ids": [(6, 0, user.ids)],
            "access_line_ids": [(0, 0, {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "perm_read": True,
            })],
            "rule_line_ids": [(0, 0, {
                "name": "Own company contacts",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "domain_force": "[('company_id', 'in', [False, company_id])]",
            })],
        })
        profile.action_apply()
        group_field = "group_ids" if "group_ids" in user._fields else "groups_id"
        self.assertIn(profile.generated_group_id, user[group_field])
        self.assertTrue(profile.access_line_ids.native_access_id)
        self.assertTrue(profile.rule_line_ids.native_rule_id)
        self.assertEqual(profile.state, "applied")
        self.assertEqual(len(self.env["ow.access.audit"].search([("profile_id", "=", profile.id)])), 1)

    def test_invalid_rule_domain_is_rejected(self):
        profile = self.env["ow.access.profile"].create({"name": "Invalid Rule Test"})
        with self.assertRaises(Exception):
            self.env["ow.access.rule.line"].create({
                "profile_id": profile.id,
                "name": "Invalid",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "domain_force": "not a domain",
            })
