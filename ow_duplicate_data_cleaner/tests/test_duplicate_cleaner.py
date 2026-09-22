from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDuplicateCleaner(TransactionCase):
    def setUp(self):
        super().setUp()
        self.rule = self.env.ref("ow_duplicate_data_cleaner.rule_contacts")
        self.env.ref("base.user_admin").write({
            "group_ids": [(4, self.env.ref("ow_duplicate_data_cleaner.group_duplicate_manager").id)]
        })

    def test_scan_and_native_partner_merge(self):
        first, second = self.env["res.partner"].create([
            {"name": "Northwind Trading", "email": "hello@northwind.example", "phone": "+1 555 222 3344"},
            {"name": "Northwind Trading Ltd", "email": " HELLO@northwind.example ", "phone": "(555) 222-3344"},
        ])
        action = self.rule.action_scan_now()
        scan = self.env["ow.duplicate.scan"].browse(action["res_id"])
        group = scan.group_ids.filtered(lambda candidate: first.id in candidate.member_ids.mapped("res_id") and second.id in candidate.member_ids.mapped("res_id"))
        self.assertEqual(scan.state, "done")
        self.assertEqual(len(group), 1)
        master_member = group.member_ids.filtered(lambda member: member.res_id == first.id)
        wizard = self.env["ow.duplicate.merge.wizard"].create({
            "group_id": group.id,
            "master_member_id": master_member.id,
        })
        wizard.with_user(self.env.ref("base.user_admin")).action_merge()
        self.assertTrue(first.exists())
        self.assertFalse(second.exists())
        self.assertEqual(group.status, "merged")
        self.assertTrue(group.merge_log_id)

    def test_normalizers(self):
        self.assertEqual(self.rule._normalize(" User@Example.COM ", "email"), "user@example.com")
        self.assertEqual(self.rule._normalize("+91 (98765) 43210", "phone"), "9876543210")
        self.assertEqual(self.rule._normalize(" VAT-12 / AB ", "alphanumeric"), "vat12ab")
