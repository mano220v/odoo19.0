from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class DuplicateMergeWizard(models.TransientModel):
    _name = "ow.duplicate.merge.wizard"
    _description = "Review and Merge Duplicate Records"

    group_id = fields.Many2one("ow.duplicate.group", required=True, readonly=True)
    member_ids = fields.One2many(related="group_id.member_ids", readonly=True)
    master_member_id = fields.Many2one("ow.duplicate.member", required=True)
    disposition = fields.Selection(
        [("archive", "Archive duplicate records"), ("delete", "Permanently delete duplicate records")],
        default="archive", required=True,
    )
    fill_missing_values = fields.Boolean(
        default=True,
        help="Copy empty writable fields on the master from the duplicate records before archiving or deleting them.",
    )
    confirmation = fields.Char(help="Enter DELETE when permanent deletion is selected.")
    warning_message = fields.Text(compute="_compute_warning_message")

    @api.depends("group_id", "disposition")
    def _compute_warning_message(self):
        for wizard in self:
            if wizard.group_id.model_name == "res.partner":
                wizard.warning_message = _("Contacts use Odoo's native partner merge engine. Linked documents and references are transferred to the selected master.")
            elif wizard.disposition == "delete":
                wizard.warning_message = _("Permanent deletion cannot be undone. References will be reassigned first; any unsafe reference update stops the merge.")
            else:
                wizard.warning_message = _("References will be reassigned to the master and duplicate records will be archived. This is the recommended reversible option.")

    @api.onchange("group_id")
    def _onchange_group_id(self):
        if self.group_id:
            suggested = self.group_id.member_ids.filtered("is_suggested_master")[:1]
            self.master_member_id = suggested or self.group_id.member_ids[:1]

    @api.constrains("master_member_id", "group_id")
    def _check_master_member(self):
        for wizard in self:
            if wizard.master_member_id and wizard.master_member_id.group_id != wizard.group_id:
                raise ValidationError(_("The master record must belong to this duplicate group."))

    def action_merge(self):
        self.ensure_one()
        if not self.env.user.has_group("ow_duplicate_data_cleaner.group_duplicate_manager"):
            raise AccessError(_("Only Duplicate Data Cleaner Managers can merge records."))
        group = self.group_id
        if group.status != "open":
            raise UserError(_("This duplicate group has already been processed."))
        if self.disposition == "delete" and self.confirmation != "DELETE":
            raise UserError(_("Enter DELETE to confirm permanent record deletion."))

        model = self.env[group.model_name].sudo().with_context(active_test=False)
        master = model.browse(self.master_member_id.res_id).exists()
        sources = model.browse((group.member_ids - self.master_member_id).mapped("res_id")).exists()
        if not master or not sources:
            raise UserError(_("The master or duplicate records no longer exist. Run a fresh scan."))
        if len(sources) > 20:
            raise UserError(_("For safety, merge no more than 20 duplicate records at a time."))

        source_names = ", ".join(sources.mapped("display_name"))
        reference_count = copied_count = 0
        details = []
        disposition = self.disposition

        if group.model_name == "res.partner":
            merge_model = self.env["base.partner.merge.automatic.wizard"].sudo()
            remaining = list(sources.ids)
            while remaining:
                chunk = remaining[:2]
                remaining = remaining[2:]
                merge_model._merge([master.id, *chunk], dst_partner=master, extra_checks=False)
            disposition = "native"
            details.append(_("Merged through Odoo's native contact merge engine."))
        else:
            if self.fill_missing_values:
                copied_count, copied_details = self._copy_missing_values(master, sources)
                details.extend(copied_details)
            reference_count, reference_details, failures = self._reassign_references(master, sources)
            details.extend(reference_details)
            if failures and self.disposition == "delete":
                raise UserError(_("Permanent deletion stopped because some references could not be reassigned:\n%s") % "\n".join(failures))
            details.extend(failures)
            if self.disposition == "archive":
                if "active" not in model._fields:
                    raise UserError(_("This model has no Active field. Choose permanent deletion after reviewing the reference report."))
                sources.write({"active": False})
            else:
                sources.unlink()

        log = self.env["ow.duplicate.merge.log"].create({
            "name": _("Merge %s into %s") % (source_names, master.display_name),
            "company_id": group.company_id.id,
            "group_id": group.id,
            "rule_id": group.rule_id.id,
            "model_name": group.model_name,
            "master_res_id": master.id,
            "master_name": master.display_name,
            "source_res_ids": ",".join(str(record_id) for record_id in sources.ids),
            "source_names": source_names,
            "disposition": disposition,
            "reference_count": reference_count,
            "copied_field_count": copied_count,
            "details": "\n".join(details),
        })
        group.write({
            "status": "merged", "merged_at": fields.Datetime.now(),
            "merged_by": self.env.user.id, "merge_log_id": log.id,
        })
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {
                "title": _("Duplicates merged"),
                "message": _("%s record(s) were consolidated into %s.") % (len(sources), master.display_name),
                "type": "success", "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _copy_missing_values(self, master, sources):
        copied = 0
        details = []
        protected = {"id", "display_name", "create_uid", "create_date", "write_uid", "write_date", "active", "company_id"}
        for field_name, field in master._fields.items():
            if field_name in protected or field.compute or not field.store or field.readonly or field.type in ("one2many", "many2many", "binary"):
                continue
            try:
                if master[field_name]:
                    continue
                source = sources.filtered(lambda record: bool(record[field_name]))[:1]
                if not source:
                    continue
                value = source[field_name]
                if field.type == "many2one":
                    value = value.id
                with self.env.cr.savepoint():
                    master.write({field_name: value})
                copied += 1
                details.append(_("Copied field %s from %s.") % (field.string, source.display_name))
            except Exception as exc:
                details.append(_("Skipped field %s: %s") % (field.string, exc))
        return copied, details

    def _reassign_references(self, master, sources):
        count = 0
        details = []
        failures = []
        source_ids = sources.ids
        field_records = self.env["ir.model.fields"].sudo().search([
            ("relation", "=", master._name),
            ("ttype", "in", ["many2one", "many2many"]),
            ("store", "=", True),
        ])
        for field_record in field_records:
            if field_record.model not in self.env.registry.models:
                continue
            target_model = self.env[field_record.model].sudo().with_context(active_test=False)
            field = target_model._fields.get(field_record.name)
            if not field or field.compute or field.readonly:
                continue
            try:
                references = target_model.search([(field_record.name, "in", source_ids)])
                if not references:
                    continue
                with self.env.cr.savepoint():
                    if field_record.ttype == "many2one":
                        references.write({field_record.name: master.id})
                        count += len(references)
                    else:
                        for reference in references:
                            current_ids = reference[field_record.name].ids
                            new_ids = list(dict.fromkeys([master.id if item in source_ids else item for item in current_ids]))
                            reference.write({field_record.name: [(6, 0, new_ids)]})
                            count += 1
                details.append(_("Reassigned %s reference(s) in %s.%s.") % (len(references), field_record.model, field_record.name))
            except Exception as exc:
                failures.append(_("Could not update %s.%s: %s") % (field_record.model, field_record.name, exc))
        return count, details, failures
