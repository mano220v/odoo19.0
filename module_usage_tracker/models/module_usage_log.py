from odoo import api, fields, models


class ModuleUsageLog(models.Model):
    _name = "module.usage.log"
    _description = "Module Usage Log"
    _order = "start_datetime desc, id desc"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="cascade",
    )
    module_name = fields.Char(required=True, index=True)
    module_xmlid = fields.Char(index=True)
    menu_id = fields.Integer(index=True)
    action_id = fields.Char(index=True)
    tab_uuid = fields.Char(index=True)
    start_datetime = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    end_datetime = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    duration_seconds = fields.Integer(required=True, default=0, index=True)
    duration_display = fields.Char(compute="_compute_duration_display")

    @api.depends("duration_seconds")
    def _compute_duration_display(self):
        for record in self:
            seconds = max(record.duration_seconds or 0, 0)
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                record.duration_display = "%sh %sm" % (hours, minutes)
            elif minutes:
                record.duration_display = "%sm %ss" % (minutes, seconds)
            else:
                record.duration_display = "%ss" % seconds

    @api.model
    def _format_duration(self, seconds):
        seconds = int(seconds or 0)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return "%sh %sm" % (hours, minutes)
        if minutes:
            return "%sm %ss" % (minutes, seconds)
        return "%ss" % seconds
