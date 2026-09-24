import time
from collections import defaultdict
from itertools import combinations

from odoo import api, fields, models, _


class DuplicateScan(models.Model):
    _name = "ow.duplicate.scan"
    _description = "Duplicate Data Scan"
    _order = "started_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    rule_id = fields.Many2one("ow.duplicate.rule", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    model_name = fields.Char(related="rule_id.model_name", store=True)
    state = fields.Selection(
        [("running", "Running"), ("done", "Completed"), ("failed", "Failed")],
        default="running", required=True, index=True,
    )
    started_at = fields.Datetime(default=fields.Datetime.now, required=True)
    finished_at = fields.Datetime()
    duration = fields.Float(string="Duration (seconds)", digits=(12, 3))
    scanned_record_count = fields.Integer()
    compared_pair_count = fields.Integer()
    duplicate_group_count = fields.Integer()
    duplicate_record_count = fields.Integer()
    group_ids = fields.One2many("ow.duplicate.group", "scan_id")
    error_message = fields.Text()

    @api.depends("rule_id.name", "started_at")
    def _compute_name(self):
        for scan in self:
            scan.name = "%s · %s" % (
                scan.rule_id.name or _("Duplicate Scan"),
                fields.Datetime.to_string(scan.started_at) if scan.started_at else "",
            )

    def _execute_scan(self):
        self.ensure_one()
        started = time.monotonic()
        try:
            rule = self.rule_id
            model = self.env[rule.model_name].sudo().with_context(active_test=False)
            records = model.search(rule._scan_domain(), limit=rule.maximum_records + 1, order="id")
            if len(records) > rule.maximum_records:
                records = records[:rule.maximum_records]

            normalized = {record.id: rule._record_values(record) for record in records}
            blocks = defaultdict(set)
            fuzzy_lines = rule.field_line_ids.filtered(lambda line: line.match_type == "fuzzy")
            exact_lines = rule.field_line_ids.filtered(lambda line: line.match_type == "exact")
            for record in records:
                values = normalized[record.id]
                for line in exact_lines:
                    value = values.get(line.field_id.name)
                    if value:
                        blocks["e:%s:%s" % (line.field_id.name, value)].add(record.id)
                for line in fuzzy_lines:
                    value = values.get(line.field_id.name)
                    if value:
                        blocks["f:%s:%s" % (line.field_id.name, value[:3])].add(record.id)

            parent = {record.id: record.id for record in records}

            def find(item):
                while parent[item] != item:
                    parent[item] = parent[parent[item]]
                    item = parent[item]
                return item

            def union(left, right):
                left_root, right_root = find(left), find(right)
                if left_root != right_root:
                    parent[right_root] = left_root

            checked_pairs = set()
            match_scores = {}
            match_reasons = defaultdict(list)
            for ids in blocks.values():
                if len(ids) < 2:
                    continue
                for left, right in combinations(sorted(ids), 2):
                    pair = (left, right)
                    if pair in checked_pairs:
                        continue
                    checked_pairs.add(pair)
                    score, reasons = rule._score_pair(normalized[left], normalized[right])
                    if score >= rule.minimum_confidence:
                        union(left, right)
                        match_scores[pair] = score
                        match_reasons[pair] = reasons

            components = defaultdict(list)
            for record in records:
                components[find(record.id)].append(record.id)

            created_groups = self.env["ow.duplicate.group"]
            for record_ids in components.values():
                if len(record_ids) < 2:
                    continue
                component_pairs = [pair for pair in match_scores if pair[0] in record_ids and pair[1] in record_ids]
                confidence = sum(match_scores[pair] for pair in component_pairs) / len(component_pairs) if component_pairs else 0
                reasons = sorted({reason for pair in component_pairs for reason in match_reasons[pair]})
                component_records = model.browse(record_ids).exists()
                master = max(component_records, key=lambda rec: (self._completeness(rec, rule), -rec.id))
                group = self.env["ow.duplicate.group"].create({
                    "scan_id": self.id,
                    "rule_id": rule.id,
                    "company_id": self.company_id.id,
                    "model_name": rule.model_name,
                    "confidence": confidence,
                    "match_reason": ", ".join(reasons)[:2000],
                    "suggested_master_res_id": master.id,
                })
                for record in component_records:
                    self.env["ow.duplicate.member"].create({
                        "group_id": group.id,
                        "model_name": rule.model_name,
                        "res_id": record.id,
                        "record_name": record.display_name,
                        "is_suggested_master": record.id == master.id,
                        "completeness_score": self._completeness(record, rule),
                        "value_preview": self._preview_values(record, rule),
                        "normalized_values": normalized[record.id],
                    })
                created_groups |= group

            self.write({
                "state": "done", "finished_at": fields.Datetime.now(),
                "duration": time.monotonic() - started,
                "scanned_record_count": len(records),
                "compared_pair_count": len(checked_pairs),
                "duplicate_group_count": len(created_groups),
                "duplicate_record_count": sum(created_groups.mapped("member_count")),
            })
        except Exception as exc:
            self.write({
                "state": "failed", "finished_at": fields.Datetime.now(),
                "duration": time.monotonic() - started, "error_message": str(exc),
            })
            raise
        return self

    @staticmethod
    def _completeness(record, rule):
        score = 0
        for field_name, field in record._fields.items():
            if field_name in ("id", "create_uid", "write_uid", "create_date", "write_date"):
                continue
            if field.store and not field.compute and field.type not in ("one2many", "binary"):
                try:
                    if record[field_name]:
                        score += 1
                except Exception:
                    pass
        return score

    @staticmethod
    def _preview_values(record, rule):
        parts = []
        for line in rule.field_line_ids.sorted("sequence"):
            value = record[line.field_id.name]
            if hasattr(value, "display_name"):
                value = value.display_name
            parts.append("%s: %s" % (line.field_id.field_description, value or "—"))
        return " · ".join(parts)[:2000]

    def action_view_groups(self):
        self.ensure_one()
        action = self.env.ref("ow_duplicate_data_cleaner.action_duplicate_group").read()[0]
        action["domain"] = [("scan_id", "=", self.id)]
        return action
