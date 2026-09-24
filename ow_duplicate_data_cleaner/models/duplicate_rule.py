import re
import unicodedata
import logging
from difflib import SequenceMatcher

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


SUPPORTED_FIELD_TYPES = {
    "char", "text", "integer", "float", "monetary", "many2one", "date", "datetime"
}

_logger = logging.getLogger(__name__)


class DuplicateRule(models.Model):
    _name = "ow.duplicate.rule"
    _description = "Duplicate Detection Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, index=True)
    model_id = fields.Many2one(
        "ir.model", required=True, ondelete="cascade", tracking=True,
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(string="Technical Model", related="model_id.model", store=True, index=True)
    field_line_ids = fields.One2many("ow.duplicate.rule.field", "rule_id", string="Matching Fields", copy=True)
    domain_filter = fields.Char(
        default="[]", required=True,
        help="Optional Odoo domain limiting records included in this scan.",
    )
    include_archived = fields.Boolean()
    company_scope = fields.Selection(
        [("current", "Current Company"), ("allowed", "All Allowed Companies"), ("all", "All Companies")],
        default="current", required=True,
    )
    minimum_confidence = fields.Float(default=80.0, required=True)
    maximum_records = fields.Integer(default=5000, required=True)
    scheduled_scan = fields.Boolean(default=False)
    scan_ids = fields.One2many("ow.duplicate.scan", "rule_id")
    scan_count = fields.Integer(compute="_compute_scan_stats")
    open_group_count = fields.Integer(compute="_compute_scan_stats")
    duplicate_record_count = fields.Integer(compute="_compute_scan_stats")
    last_scan_at = fields.Datetime(compute="_compute_scan_stats")
    last_scan_state = fields.Selection(
        [("running", "Running"), ("done", "Completed"), ("failed", "Failed")],
        compute="_compute_scan_stats",
    )

    @api.depends("scan_ids", "scan_ids.state", "scan_ids.group_ids.status")
    def _compute_scan_stats(self):
        for rule in self:
            scans = rule.scan_ids.sorted("started_at", reverse=True)
            latest = scans[:1]
            open_groups = scans.mapped("group_ids").filtered(lambda group: group.status == "open")
            rule.scan_count = len(scans)
            rule.open_group_count = len(open_groups)
            rule.duplicate_record_count = sum(open_groups.mapped("member_count"))
            rule.last_scan_at = latest.started_at if latest else False
            rule.last_scan_state = latest.state if latest else False

    @api.constrains("minimum_confidence", "maximum_records")
    def _check_limits(self):
        for rule in self:
            if not 1 <= rule.minimum_confidence <= 100:
                raise ValidationError(_("Minimum confidence must be between 1 and 100."))
            if not 2 <= rule.maximum_records <= 50000:
                raise ValidationError(_("Maximum records must be between 2 and 50,000."))

    @api.constrains("domain_filter")
    def _check_domain_filter(self):
        for rule in self:
            try:
                domain = safe_eval(rule.domain_filter or "[]", {"uid": self.env.uid})
                if not isinstance(domain, (list, tuple)):
                    raise ValueError
            except Exception as exc:
                raise ValidationError(_("Domain Filter must be a valid Odoo domain.")) from exc

    def _scan_domain(self):
        self.ensure_one()
        domain = list(safe_eval(self.domain_filter or "[]", {"uid": self.env.uid}))
        model = self.env[self.model_name]
        if "active" in model._fields and not self.include_archived:
            domain.append(("active", "=", True))
        if "company_id" in model._fields:
            if self.company_scope == "current":
                domain.append(("company_id", "in", [False, self.company_id.id]))
            elif self.company_scope == "allowed":
                domain.append(("company_id", "in", [False, *self.env.companies.ids]))
        return domain

    @staticmethod
    def _normalize(value, mode):
        if hasattr(value, "id"):
            value = value.id
        if value in (False, None, ""):
            return ""
        text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
        text = text.strip().lower()
        if mode == "email":
            return re.sub(r"\s+", "", text)
        if mode == "phone":
            digits = re.sub(r"\D", "", text)
            return digits[-10:] if len(digits) > 10 else digits
        if mode == "alphanumeric":
            return re.sub(r"[^a-z0-9]", "", text)
        if mode == "whitespace":
            return re.sub(r"\s+", " ", text)
        if mode == "numbers":
            return re.sub(r"\D", "", text)
        return text

    def _record_values(self, record):
        values = {}
        for line in self.field_line_ids.sorted("sequence"):
            values[line.field_id.name] = self._normalize(record[line.field_id.name], line.normalization)
        return values

    def _score_pair(self, first, second):
        total_weight = 0.0
        total_score = 0.0
        reasons = []
        for line in self.field_line_ids:
            left = first.get(line.field_id.name, "")
            right = second.get(line.field_id.name, "")
            if not left or not right:
                if line.required_match:
                    return 0.0, []
                continue
            if line.match_type == "exact":
                score = 100.0 if left == right else 0.0
            else:
                score = SequenceMatcher(None, left, right).ratio() * 100.0
            if line.required_match and score < line.threshold:
                return 0.0, []
            weight = line.weight or 1.0
            total_weight += weight
            total_score += score * weight
            if score >= line.threshold:
                reasons.append("%s %.0f%%" % (line.field_id.field_description, score))
        if not total_weight:
            return 0.0, []
        return total_score / total_weight, reasons

    def action_scan_now(self):
        self.ensure_one()
        if not self.field_line_ids:
            raise UserError(_("Add at least one matching field before scanning."))
        invalid = self.field_line_ids.filtered(lambda line: line.field_id.model != self.model_name)
        if invalid:
            raise UserError(_("Every matching field must belong to the selected model."))
        scan = self.env["ow.duplicate.scan"].create({
            "rule_id": self.id,
            "company_id": self.company_id.id,
            "state": "running",
            "started_at": fields.Datetime.now(),
        })
        scan._execute_scan()
        return {
            "type": "ir.actions.act_window",
            "name": _("Duplicate Scan"),
            "res_model": "ow.duplicate.scan",
            "res_id": scan.id,
            "view_mode": "form",
        }

    def action_view_scans(self):
        self.ensure_one()
        action = self.env.ref("ow_duplicate_data_cleaner.action_duplicate_scan").read()[0]
        action["domain"] = [("rule_id", "=", self.id)]
        return action

    @api.model
    def _cron_run_scheduled_scans(self):
        for rule in self.search([("active", "=", True), ("scheduled_scan", "=", True)]):
            try:
                with self.env.cr.savepoint():
                    scan = self.env["ow.duplicate.scan"].create({
                        "rule_id": rule.id, "company_id": rule.company_id.id,
                        "state": "running", "started_at": fields.Datetime.now(),
                    })
                    scan._execute_scan()
            except Exception:
                _logger.exception("Scheduled duplicate scan failed for rule %s", rule.display_name)


class DuplicateRuleField(models.Model):
    _name = "ow.duplicate.rule.field"
    _description = "Duplicate Matching Field"
    _order = "sequence, id"

    rule_id = fields.Many2one("ow.duplicate.rule", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    model_id = fields.Many2one(related="rule_id.model_id")
    field_id = fields.Many2one(
        "ir.model.fields", required=True, ondelete="cascade",
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['char','text','integer','float','monetary','many2one','date','datetime'])]",
    )
    match_type = fields.Selection([("exact", "Exact"), ("fuzzy", "Fuzzy")], default="exact", required=True)
    normalization = fields.Selection([
        ("standard", "Lowercase & accents"), ("whitespace", "Normalize whitespace"),
        ("email", "Email"), ("phone", "Phone"),
        ("alphanumeric", "Letters & numbers only"), ("numbers", "Numbers only"),
    ], default="standard", required=True)
    weight = fields.Float(default=1.0, required=True)
    threshold = fields.Float(default=85.0, required=True)
    required_match = fields.Boolean(help="Reject a pair unless this field reaches its threshold.")

    @api.constrains("weight", "threshold")
    def _check_values(self):
        for line in self:
            if line.weight <= 0:
                raise ValidationError(_("Field weight must be greater than zero."))
            if not 1 <= line.threshold <= 100:
                raise ValidationError(_("Field threshold must be between 1 and 100."))
