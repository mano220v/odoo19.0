import io
import pytz
import logging
import xlsxwriter
from datetime import datetime, time, timedelta
from collections import defaultdict
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
    def _get_user_tz(self):
        env = request.env
        tz_name = (
            env.user.partner_id.tz
            or env.company.partner_id.tz
            or 'UTC'
        )
        return pytz.timezone(tz_name)

    def _day_utc_bounds(self, date_obj, user_tz):
        """Return (start_utc_str, end_utc_str) for a local date."""
        start_utc = (
            user_tz.localize(datetime.combine(date_obj, time.min))
            .astimezone(pytz.utc).replace(tzinfo=None)
        )
        end_utc = (
            user_tz.localize(datetime.combine(date_obj, time.max))
            .astimezone(pytz.utc).replace(tzinfo=None)
        )
        return (
            fields.Datetime.to_string(start_utc),
            fields.Datetime.to_string(end_utc),
        )

    @http.route(
        '/hr_dashboard_odoo_wings/get_attendance_data',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def get_attendance_data(self):
        env = request.env
        user_tz = self._get_user_tz()

        now_local   = datetime.now(user_tz)
        today_local = now_local.date()

        today_start_str, today_end_str = self._day_utc_bounds(today_local, user_tz)

        # ── All active employees in the current company ────────────────────
        all_employees = env['hr.employee'].sudo().search([
            ('active',     '=', True),
            ('company_id', '=', env.company.id),
        ])
        all_emp_ids = all_employees.ids

        emp_dept = {}
        dept_meta = {}
        for emp in all_employees:
            dept_id   = emp.department_id.id   if emp.department_id else 0
            dept_name = emp.department_id.name if emp.department_id else 'No Department'
            emp_dept[emp.id] = {'id': dept_id, 'name': dept_name}
            dept_meta[dept_id] = dept_name

        # Present
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
                if l.employee_id.id not in present_ids
            })
        except Exception:
            _logger.warning("hr_dashboard: could not query hr.leave", exc_info=True)
            on_leave_ids_raw = []

        # Absent
        excluded   = set(present_ids) | set(on_leave_ids_raw)
        absent_ids = [eid for eid in all_emp_ids if eid not in excluded]

        # Dept breakdown
        present_set  = set(present_ids)
        on_leave_set = set(on_leave_ids_raw)

        dept_present  = defaultdict(list)
        dept_on_leave = defaultdict(list)
        dept_absent   = defaultdict(list)
        dept_total    = defaultdict(int)

        for emp_id in all_emp_ids:
            dept_id = emp_dept[emp_id]['id']
            dept_total[dept_id] += 1
            if emp_id in present_set:
                dept_present[dept_id].append(emp_id)
            elif emp_id in on_leave_set:
                dept_on_leave[dept_id].append(emp_id)
            else:
                dept_absent[dept_id].append(emp_id)

        sorted_dept_ids = sorted(
            dept_meta.keys(),
            key=lambda d: (d == 0, dept_meta[d].lower())
        )

        departments = []
        for dept_id in sorted_dept_ids:
            p_ids = dept_present[dept_id]
            l_ids = dept_on_leave[dept_id]
            a_ids = dept_absent[dept_id]
            tot   = dept_total[dept_id]
            departments.append({
                'id':             dept_id,
                'name':           dept_meta[dept_id],
                'total':          tot,
                'present_count':  len(p_ids),
                'on_leave_count': len(l_ids),
                'absent_count':   len(a_ids),
                'present_ids':    p_ids,
                'on_leave_ids':   l_ids,
                'absent_ids':     a_ids,
            })

        return {
            'total':          len(all_emp_ids),
            'present_count':  len(present_ids),
            'on_leave_count': len(on_leave_ids_raw),
            'absent_count':   len(absent_ids),
            'present_ids':    present_ids,
            'on_leave_ids':   on_leave_ids_raw,
            'absent_ids':     absent_ids,
            'departments':    departments,
            'today_start':    today_start_str,
            'today_end':      today_end_str,
            'today_label':    today_local.strftime('%d %B %Y'),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # New: Export attendance to Excel (HTTP GET → file download)
    # ─────────────────────────────────────────────────────────────────────────
    @http.route(
        '/hr_dashboard_odoo_wings/export_attendance',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
    )
    def export_attendance(self, date_type='current', from_date=None, to_date=None, **kwargs):
        env     = request.env
        user_tz = self._get_user_tz()
        today   = datetime.now(user_tz).date()

        # ── Resolve date range ───────────────────────────────────────────────
        if date_type == 'current':
            from_date_obj = to_date_obj = today
            file_label    = today.strftime('%d_%b_%Y')
        else:
            try:
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
                to_date_obj   = datetime.strptime(to_date,   '%Y-%m-%d').date()
                if from_date_obj > to_date_obj:
                    from_date_obj, to_date_obj = to_date_obj, from_date_obj
            except Exception:
                from_date_obj = to_date_obj = today
            file_label = (
                f"{from_date_obj.strftime('%d_%b_%Y')}"
                f"_to_{to_date_obj.strftime('%d_%b_%Y')}"
            )

        # ── All active employees ─────────────────────────────────────────────
        all_employees = env['hr.employee'].sudo().search([
            ('active',     '=', True),
            ('company_id', '=', env.company.id),
        ], order='name asc')

        # ── Fetch attendance for the whole range in ONE query ────────────────
        range_start_str, _          = self._day_utc_bounds(from_date_obj, user_tz)
        _,               range_end_str = self._day_utc_bounds(to_date_obj,   user_tz)

        all_atts = env['hr.attendance'].sudo().search([
            ('check_in',    '>=', range_start_str),
            ('check_in',    '<=', range_end_str),
            ('employee_id', 'in', all_employees.ids),
        ])

        # Map: (emp_id, local_date) → [attendance, ...]
        att_map = defaultdict(list)
        for att in all_atts:
            local_date = (
                pytz.utc.localize(att.check_in)
                .astimezone(user_tz).date()
            )
            att_map[(att.employee_id.id, local_date)].append(att)

        # ── Fetch approved leaves for the whole range in ONE query ───────────
        leave_day_set = set()   # {(emp_id, date)}
        try:
            all_leaves = env['hr.leave'].sudo().search([
                ('state',       '=', 'validate'),
                ('date_from',   '<=', range_end_str),
                ('date_to',     '>=', range_start_str),
                ('employee_id', 'in', all_employees.ids),
            ])
            for lv in all_leaves:
                # date_from / date_to are datetime (UTC) in Odoo 16+
                lf = (pytz.utc.localize(lv.date_from).astimezone(user_tz).date()
                      if isinstance(lv.date_from, datetime) else lv.date_from)
                lt = (pytz.utc.localize(lv.date_to).astimezone(user_tz).date()
                      if isinstance(lv.date_to, datetime) else lv.date_to)
                d = max(lf, from_date_obj)
                while d <= min(lt, to_date_obj):
                    leave_day_set.add((lv.employee_id.id, d))
                    d += timedelta(days=1)
        except Exception:
            _logger.warning("hr_dashboard export: could not query hr.leave", exc_info=True)

        # ── Build date list ──────────────────────────────────────────────────
        dates = []
        d = from_date_obj
        while d <= to_date_obj:
            dates.append(d)
            d += timedelta(days=1)

        # ════════════════════════════════════════════════════════════════════
        # Build Excel workbook
        # ════════════════════════════════════════════════════════════════════
        output   = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws       = workbook.add_worksheet('Attendance Report')
        ws.set_zoom(90)

        # ── Formats ─────────────────────────────────────────────────────────
        def fmt(**kw):
            defaults = {'border': 1, 'valign': 'vcenter', 'font_name': 'Arial', 'font_size': 10}
            defaults.update(kw)
            return workbook.add_format(defaults)

        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'font_color': '#2d3748',
            'font_name': 'Arial',
        })
        sub_fmt = workbook.add_format({
            'font_size': 10, 'font_color': '#718096', 'font_name': 'Arial',
        })
        hdr_fmt = fmt(
            bold=True, bg_color='#4e73df', font_color='#FFFFFF',
            align='center', font_size=11,
        )
        cell_fmt  = fmt(align='left')
        num_fmt   = fmt(align='center')
        time_fmt  = fmt(align='center', font_color='#4a5568')
        even_fmt  = fmt(align='left',   bg_color='#f7fafc')
        even_num  = fmt(align='center', bg_color='#f7fafc')
        even_time = fmt(align='center', bg_color='#f7fafc', font_color='#4a5568')

        present_y = fmt(align='center', bold=True, bg_color='#c6efce', font_color='#276221')
        present_n = fmt(align='center', font_color='#a0aec0')
        absent_y  = fmt(align='center', bold=True, bg_color='#ffc7ce', font_color='#9c0006')
        absent_n  = fmt(align='center', font_color='#a0aec0')
        leave_y   = fmt(align='center', bold=True, bg_color='#ffeb9c', font_color='#7d5a00')
        leave_n   = fmt(align='center', font_color='#a0aec0')

        # ── Column widths ────────────────────────────────────────────────────
        ws.set_column(0, 0,  7)   # Sl No
        ws.set_column(1, 1, 26)   # Employee Name
        ws.set_column(2, 2, 22)   # Department
        ws.set_column(3, 3, 22)   # Shift / Schedule
        ws.set_column(4, 4, 14)   # Date
        ws.set_column(5, 5, 14)   # Check-in
        ws.set_column(6, 6, 14)   # Check-out
        ws.set_column(7, 7, 10)   # Present
        ws.set_column(8, 8, 10)   # Absent
        ws.set_column(9, 9, 10)   # On Leave
        ws.set_row(0, 22)
        ws.set_row(1, 16)
        ws.set_row(3, 20)

        # ── Title ────────────────────────────────────────────────────────────
        ws.merge_range('A1:J1', 'Employee Attendance Report', title_fmt)
        if date_type == 'current':
            period_txt = f"Date: {from_date_obj.strftime('%d %B %Y')}"
        else:
            period_txt = (
                f"Period: {from_date_obj.strftime('%d %B %Y')}"
                f"  →  {to_date_obj.strftime('%d %B %Y')}"
                f"  |  {len(dates)} day(s)  |  {len(all_employees)} employee(s)"
            )
        ws.merge_range('A2:J2', period_txt, sub_fmt)

        # ── Header row (row index 3) ─────────────────────────────────────────
        headers = [
            'Sl No', 'Employee Name', 'Department', 'Shift / Schedule',
            'Date', 'Check-in', 'Check-out', 'Present', 'Absent', 'On Leave',
        ]
        for col, h in enumerate(headers):
            ws.write(3, col, h, hdr_fmt)

        # ── Data rows ────────────────────────────────────────────────────────
        row  = 4
        sl   = 1

        for date_obj in dates:
            for emp in all_employees:
                is_even = (sl % 2 == 0)

                # Attendance records for this employee on this date
                emp_atts = sorted(
                    att_map.get((emp.id, date_obj), []),
                    key=lambda a: a.check_in
                )

                is_present  = bool(emp_atts)
                is_on_leave = (emp.id, date_obj) in leave_day_set and not is_present
                is_absent   = not is_present and not is_on_leave

                # Check-in / Check-out (first in, last out)
                check_in_str  = ''
                check_out_str = ''
                if emp_atts:
                    ci = emp_atts[0].check_in
                    if ci:
                        check_in_str = (
                            pytz.utc.localize(ci)
                            .astimezone(user_tz)
                            .strftime('%I:%M %p')
                        )
                    co = emp_atts[-1].check_out
                    if co:
                        check_out_str = (
                            pytz.utc.localize(co)
                            .astimezone(user_tz)
                            .strftime('%I:%M %p')
                        )

                dept_name  = emp.department_id.name         if emp.department_id         else ''
                shift_name = emp.resource_calendar_id.name  if emp.resource_calendar_id  else ''
                date_str   = date_obj.strftime('%d-%m-%Y')

                # Choose row formats
                cf   = even_fmt  if is_even else cell_fmt
                nf   = even_num  if is_even else num_fmt
                tf   = even_time if is_even else time_fmt

                ws.write(row, 0, sl,             nf)
                ws.write(row, 1, emp.name,       cf)
                ws.write(row, 2, dept_name,      cf)
                ws.write(row, 3, shift_name,     cf)
                ws.write(row, 4, date_str,       nf)
                ws.write(row, 5, check_in_str,   tf)
                ws.write(row, 6, check_out_str,  tf)

                # Status columns
                if is_present:
                    ws.write(row, 7, 'Yes', present_y)
                    ws.write(row, 8, 'No',  absent_n)
                    ws.write(row, 9, 'No',  leave_n)
                elif is_on_leave:
                    ws.write(row, 7, 'No',  present_n)
                    ws.write(row, 8, 'No',  absent_n)
                    ws.write(row, 9, 'Yes', leave_y)
                else:
                    ws.write(row, 7, 'No',  present_n)
                    ws.write(row, 8, 'Yes', absent_y)
                    ws.write(row, 9, 'No',  leave_n)

                row += 1
                sl  += 1

        workbook.close()
        output.seek(0)

        filename = f"attendance_{file_label}.xlsx"
        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition',
                 f'attachment; filename="{filename}"'),
            ],
        )
