import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class AccessProfile(models.Model):
    _name = "ow.access.profile"
    _description = "Access Management Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    color = fields.Integer(default=4)
    description = fields.Html(sanitize=True)
    user_ids = fields.Many2many("res.users", "ow_access_profile_user_rel", "profile_id", "user_id", string="Users", tracking=True)
    implied_group_ids = fields.Many2many("res.groups", "ow_access_profile_group_rel", "profile_id", "group_id", string="Included Security Groups")
    generated_group_id = fields.Many2one("res.groups", readonly=True, copy=False, ondelete="set null")
    hidden_menu_ids = fields.Many2many("ir.ui.menu", "ow_access_profile_menu_rel", "profile_id", "menu_id", string="Hidden Menus")
    access_line_ids = fields.One2many("ow.access.model.line", "profile_id", string="Model Permissions", copy=True)
    rule_line_ids = fields.One2many("ow.access.rule.line", "profile_id", string="Record Rules", copy=True)
    field_line_ids = fields.One2many("ow.access.field.line", "profile_id", string="Field Policies", copy=True)
    user_count = fields.Integer(compute="_compute_counts")
    permission_count = fields.Integer(compute="_compute_counts")
    rule_count = fields.Integer(compute="_compute_counts")
    field_policy_count = fields.Integer(compute="_compute_counts")
    state = fields.Selection([("draft", "Draft"), ("applied", "Applied")], default="draft", required=True, tracking=True)
    last_applied_at = fields.Datetime(readonly=True, copy=False)
    last_applied_by = fields.Many2one("res.users", readonly=True, copy=False)

    @api.depends("user_ids", "access_line_ids", "rule_line_ids", "field_line_ids")
    def _compute_counts(self):
        for profile in self:
            profile.user_count = len(profile.user_ids)
            profile.permission_count = len(profile.access_line_ids)
            profile.rule_count = len(profile.rule_line_ids)
            profile.field_policy_count = len(profile.field_line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_generated_groups()
        return records

    def write(self, vals):
        result = super().write(vals)
        if set(vals) & {"name", "implied_group_ids", "user_ids", "active"}:
            self._ensure_generated_groups()
            if self.filtered(lambda p: p.state == "applied"):
                self.filtered(lambda p: p.state == "applied")._synchronize_users()
                self._clear_security_caches()
        return result

    def unlink(self):
        groups = self.mapped("generated_group_id")
        result = super().unlink()
        groups.sudo().unlink()
        self._clear_security_caches()
        return result

    def _group_category_values(self):
        group_model = self.env["res.groups"]
        if "privilege_id" in group_model._fields:
            return {"privilege_id": self.env.ref("ow_access_management_pro.privilege_access_management").id}
        return {"category_id": self.env.ref("ow_access_management_pro.module_category_access_management").id}

    def _ensure_generated_groups(self):
        for profile in self:
            values = {"name": _("Access Profile: %s") % profile.name, **profile._group_category_values()}
            if profile.generated_group_id:
                profile.generated_group_id.sudo().write(values)
            else:
                group = self.env["res.groups"].sudo().create(values)
                super(AccessProfile, profile).write({"generated_group_id": group.id})
        return True

    def _synchronize_users(self):
        for profile in self:
            profile._ensure_generated_groups()
            group = profile.generated_group_id
            user_group_field = "group_ids" if "group_ids" in self.env["res.users"]._fields else "groups_id"
            current = self.env["res.users"].sudo().with_context(active_test=False).search([(user_group_field, "in", group.ids)])
            wanted = profile.user_ids if profile.active else self.env["res.users"]
            (current - wanted).write({user_group_field: [(3, group.id)]})
            (wanted - current).write({user_group_field: [(4, group.id)]})
            group.sudo().write({"implied_ids": [(6, 0, profile.implied_group_ids.ids)]})

    def action_apply(self):
        for profile in self:
            if not profile.user_ids:
                raise UserError(_("Add at least one user before applying this profile."))
            profile._ensure_generated_groups()
            profile._synchronize_users()
            profile.access_line_ids._sync_native_records()
            profile.rule_line_ids._sync_native_records()
            profile.write({"state": "applied", "last_applied_at": fields.Datetime.now(), "last_applied_by": self.env.user.id})
            self.env["ow.access.audit"].sudo().create({
                "profile_id": profile.id, "action": "apply",
                "details": _("Applied to %s user(s), with %s model permission(s), %s record rule(s), and %s field policy/policies.") %
                    (len(profile.user_ids), len(profile.access_line_ids), len(profile.rule_line_ids), len(profile.field_line_ids)),
            })
        self._clear_security_caches()
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": _("Access profile applied"), "message": _("Security caches were refreshed and the selected users now have this profile."), "type": "success", "sticky": False}}

    def action_reset_draft(self):
        self.write({"state": "draft"})
        return True

    def action_duplicate(self):
        self.ensure_one()
        copy = self.copy({"name": _("%s (Copy)") % self.name, "state": "draft", "user_ids": [(5, 0, 0)]})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": copy.id, "view_mode": "form"}

    def action_view_users(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Profile Users"), "res_model": "res.users", "view_mode": "list,form", "domain": [("id", "in", self.user_ids.ids)]}

    @api.model
    def _clear_security_caches(self):
        if hasattr(self.env.registry, "clear_cache"):
            self.env.registry.clear_cache()
        else:
            self.env.registry.clear_caches()
        return True


class AccessModelLine(models.Model):
    _name = "ow.access.model.line"
    _description = "Access Profile Model Permission"
    _order = "model_id"

    profile_id = fields.Many2one("ow.access.profile", required=True, ondelete="cascade")
    model_id = fields.Many2one("ir.model", required=True, ondelete="cascade", domain="[('transient','=',False)]")
    model_name = fields.Char(string="Technical Model", related="model_id.model", store=True)
    perm_read = fields.Boolean(default=True)
    perm_write = fields.Boolean()
    perm_create = fields.Boolean()
    perm_unlink = fields.Boolean(string="Delete")
    native_access_id = fields.Many2one("ir.model.access", readonly=True, copy=False, ondelete="set null")

    _unique_profile_model = models.Constraint("UNIQUE(profile_id, model_id)", "A model can appear only once per profile.")

    def _sync_native_records(self):
        for line in self:
            vals = {"name": "[%s] %s" % (line.profile_id.name, line.model_id.name), "model_id": line.model_id.id, "group_id": line.profile_id.generated_group_id.id, "perm_read": line.perm_read, "perm_write": line.perm_write, "perm_create": line.perm_create, "perm_unlink": line.perm_unlink, "active": line.profile_id.active}
            if line.native_access_id:
                line.native_access_id.sudo().write(vals)
            else:
                line.native_access_id = self.env["ir.model.access"].sudo().create(vals)

    def unlink(self):
        native = self.mapped("native_access_id")
        result = super().unlink()
        native.sudo().unlink()
        self.env["ow.access.profile"]._clear_security_caches()
        return result


class AccessRuleLine(models.Model):
    _name = "ow.access.rule.line"
    _description = "Access Profile Record Rule"
    _order = "model_id, name"

    profile_id = fields.Many2one("ow.access.profile", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    model_id = fields.Many2one("ir.model", required=True, ondelete="cascade", domain="[('transient','=',False)]")
    domain_force = fields.Text(default="[]", required=True)
    perm_read = fields.Boolean(default=True)
    perm_write = fields.Boolean(default=True)
    perm_create = fields.Boolean(default=True)
    perm_unlink = fields.Boolean(default=True, string="Delete")
    native_rule_id = fields.Many2one("ir.rule", readonly=True, copy=False, ondelete="set null")

    @api.constrains("domain_force")
    def _check_domain(self):
        for line in self:
            try:
                domain = safe_eval(line.domain_force or "[]", {"user": self.env.user, "uid": self.env.uid, "company_id": self.env.company.id, "company_ids": self.env.companies.ids})
                if not isinstance(domain, (list, tuple)):
                    raise ValueError
            except Exception as exc:
                raise ValidationError(_("Record rule domain must be a valid Odoo domain.")) from exc

    def _sync_native_records(self):
        for line in self:
            vals = {"name": "[%s] %s" % (line.profile_id.name, line.name), "model_id": line.model_id.id, "domain_force": line.domain_force, "groups": [(6, 0, line.profile_id.generated_group_id.ids)], "perm_read": line.perm_read, "perm_write": line.perm_write, "perm_create": line.perm_create, "perm_unlink": line.perm_unlink, "active": line.profile_id.active}
            if line.native_rule_id:
                line.native_rule_id.sudo().write(vals)
            else:
                line.native_rule_id = self.env["ir.rule"].sudo().create(vals)

    def unlink(self):
        native = self.mapped("native_rule_id")
        result = super().unlink()
        native.sudo().unlink()
        self.env["ow.access.profile"]._clear_security_caches()
        return result


class AccessFieldLine(models.Model):
    _name = "ow.access.field.line"
    _description = "Access Profile Field Policy"
    _order = "model_id, field_id"

    profile_id = fields.Many2one("ow.access.profile", required=True, ondelete="cascade")
    model_id = fields.Many2one("ir.model", required=True, ondelete="cascade", domain="[('transient','=',False)]")
    field_id = fields.Many2one("ir.model.fields", required=True, ondelete="cascade", domain="[('model_id','=',model_id)]")
    policy = fields.Selection([("readonly", "Read-only"), ("hidden", "Hidden")], required=True, default="readonly")

    _unique_profile_field = models.Constraint("UNIQUE(profile_id, field_id)", "A field can appear only once per profile.")


class AccessAudit(models.Model):
    _name = "ow.access.audit"
    _description = "Access Management Audit"
    _order = "create_date desc, id desc"

    profile_id = fields.Many2one("ow.access.profile", required=True, ondelete="cascade", index=True)
    action = fields.Selection([("apply", "Profile Applied"), ("change", "Configuration Changed")], required=True, default="change")
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    details = fields.Text(required=True)
