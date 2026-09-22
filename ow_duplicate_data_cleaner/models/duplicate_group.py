from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DuplicateGroup(models.Model):
    _name = "ow.duplicate.group"
    _description = "Duplicate Record Group"
    _order = "confidence desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    scan_id = fields.Many2one("ow.duplicate.scan", required=True, ondelete="cascade", index=True)
    rule_id = fields.Many2one("ow.duplicate.rule", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    model_name = fields.Char(required=True, index=True)
    status = fields.Selection(
        [("open", "To Review"), ("merged", "Merged"), ("ignored", "Ignored")],
        default="open", required=True, index=True,
    )
    confidence = fields.Float(digits=(5, 2))
    match_reason = fields.Text()
    member_ids = fields.One2many("ow.duplicate.member", "group_id")
    member_count = fields.Integer(compute="_compute_member_count", store=True)
    suggested_master_res_id = fields.Integer()
    merged_at = fields.Datetime()
    merged_by = fields.Many2one("res.users")
    merge_log_id = fields.Many2one("ow.duplicate.merge.log", readonly=True)

    @api.depends("member_ids")
    def _compute_member_count(self):
        for group in self:
            group.member_count = len(group.member_ids)

    @api.depends("rule_id.name", "member_count", "confidence")
    def _compute_name(self):
        for group in self:
            group.name = _("%s · %s records · %.0f%%") % (
                group.rule_id.name or _("Duplicates"), group.member_count, group.confidence,
            )

    def action_ignore(self):
        self.write({"status": "ignored"})
        return True

    def action_reopen(self):
        self.write({"status": "open"})
        return True

    def action_open_merge_wizard(self):
        self.ensure_one()
        if self.status != "open":
            raise UserError(_("Only groups waiting for review can be merged."))
        return {
            "type": "ir.actions.act_window", "name": _("Review and Merge"),
            "res_model": "ow.duplicate.merge.wizard", "view_mode": "form", "target": "new",
            "context": {"default_group_id": self.id},
        }


class DuplicateMember(models.Model):
    _name = "ow.duplicate.member"
    _description = "Duplicate Group Member"
    _order = "is_suggested_master desc, completeness_score desc, id"

    group_id = fields.Many2one("ow.duplicate.group", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="group_id.company_id", store=True, index=True)
    model_name = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    record_name = fields.Char(required=True)
    is_suggested_master = fields.Boolean()
    completeness_score = fields.Integer()
    value_preview = fields.Text()
    normalized_values = fields.Json()
    exists = fields.Boolean(compute="_compute_exists")

    def _compute_exists(self):
        for member in self:
            member.exists = bool(self.env[member.model_name].sudo().browse(member.res_id).exists())

    def action_open_record(self):
        self.ensure_one()
        if not self.exists:
            raise UserError(_("This record no longer exists."))
        return {
            "type": "ir.actions.act_window", "res_model": self.model_name,
            "res_id": self.res_id, "view_mode": "form", "target": "current",
        }
