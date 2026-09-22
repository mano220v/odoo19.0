from odoo import fields, models


class DuplicateMergeLog(models.Model):
    _name = "ow.duplicate.merge.log"
    _description = "Duplicate Merge Audit Log"
    _order = "merged_at desc, id desc"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    group_id = fields.Many2one("ow.duplicate.group", ondelete="set null")
    rule_id = fields.Many2one("ow.duplicate.rule", ondelete="set null", index=True)
    model_name = fields.Char(required=True, index=True)
    master_res_id = fields.Integer(required=True)
    master_name = fields.Char(required=True)
    source_res_ids = fields.Char(required=True)
    source_names = fields.Text()
    disposition = fields.Selection([("archive", "Archived"), ("delete", "Deleted"), ("native", "Native Contact Merge")], required=True)
    reference_count = fields.Integer()
    copied_field_count = fields.Integer()
    merged_by = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    merged_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    details = fields.Text()

    def action_open_master(self):
        self.ensure_one()
        if not self.env[self.model_name].sudo().browse(self.master_res_id).exists():
            return False
        return {
            "type": "ir.actions.act_window", "res_model": self.model_name,
            "res_id": self.master_res_id, "view_mode": "form", "target": "current",
        }
