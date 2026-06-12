# -*- coding: utf-8 -*-
import pytz
import logging
from datetime import datetime, date, time, timedelta
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class HrAttendanceDashboardController(http.Controller):
    """
    Single JSON endpoint consumed by the OWL AttendanceDashboard component.

    Data returned
    -------------
    total           int   – all active employees in the company
    present_count   int   – employees who have at least one check-in today
    on_leave_count  int   – employees with a validated time-off covering today
                            AND who did NOT check in today
    absent_count    int   – remaining employees (no attendance, no approved leave)
    present_ids     list  – employee IDs for the present group
    on_leave_ids    list  – employee IDs for the on-leave group
    absent_ids      list  – employee IDs for the absent group
    today_start     str   – UTC datetime string for the start of today (local tz)
    today_end       str   – UTC datetime string for the end of today  (local tz)
    today_label     str   – human-readable date label, e.g. "12 June 2026"
    """

    # ------------------------------------------------------------------
    # Route
    # ------------------------------------------------------------------

    @http.route(
        '/hr_dashboard_odoo_wings/get_attendance_data',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def get_attendance_data(self):
        env = request.env

        # ── Timezone ───────────────────────────────────────────────────────
        tz_name = (
            env.user.partner_id.tz
            or env.company.partner_id.tz
            or 'UTC'
        )
        user_tz = pytz.timezone(tz_name)

        # ── Today's UTC boundaries (derived from local calendar day) ───────
        now_local   = datetime.now(user_tz)
        today_local = now_local.date()

        today_start_utc = (
            user_tz
            .localize(datetime.combine(today_local, time.min))
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )
        today_end_utc = (
            user_tz
            .localize(datetime.combine(today_local, time.max))
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )

        today_start_str = fields.Datetime.to_string(today_start_utc)
        today_end_str   = fields.Datetime.to_string(today_end_utc)

        # ── All active employees in the current company ────────────────────
        all_employees = env['hr.employee'].sudo().search([
            ('active',     '=', True),
            ('company_id', '=', env.company.id),
        ])
        all_emp_ids = all_employees.ids

        # ── Present: at least one attendance check-in today ────────────────
        today_attendances = env['hr.attendance'].sudo().search([
            ('check_in', '>=', today_start_str),
            ('check_in', '<=', today_end_str),
            ('employee_id', 'in', all_emp_ids),
        ])
        present_ids = list({a.employee_id.id for a in today_attendances})

        # ── On Leave: validated leave covering today (not already present) ──
        #   We use hr.leave (resource.calendar.leaves is unreliable for this)
        try:
            on_leave_records = env['hr.leave'].sudo().search([
                ('state',       '=', 'validate'),
                ('date_from',   '<=', today_end_str),
                ('date_to',     '>=', today_start_str),
                ('employee_id', 'in', all_emp_ids),
            ])
            on_leave_ids_raw = list({
                l.employee_id.id
                for l in on_leave_records
                if l.employee_id.id not in present_ids      # present beats on-leave
            })
        except Exception:
            _logger.warning("hr_dashboard: could not query hr.leave", exc_info=True)
            on_leave_ids_raw = []

        # ── Absent: everyone else ──────────────────────────────────────────
        excluded = set(present_ids) | set(on_leave_ids_raw)
        absent_ids = [eid for eid in all_emp_ids if eid not in excluded]

        return {
            'total':          len(all_emp_ids),
            'present_count':  len(present_ids),
            'on_leave_count': len(on_leave_ids_raw),
            'absent_count':   len(absent_ids),
            'present_ids':    present_ids,
            'on_leave_ids':   on_leave_ids_raw,
            'absent_ids':     absent_ids,
            'today_start':    today_start_str,
            'today_end':      today_end_str,
            'today_label':    today_local.strftime('%d %B %Y'),
        }
