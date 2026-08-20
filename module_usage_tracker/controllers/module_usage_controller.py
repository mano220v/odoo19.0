from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import fields, http
from odoo.http import request


class ModuleUsageTrackerController(http.Controller):
    _excluded_module_names = ("Module Usage", "Module Usage Dashboard")
    _excluded_module_xmlids = (
        "module_usage_tracker.menu_module_usage_root",
        "module_usage_tracker.menu_module_usage_dashboard",
        "module_usage_tracker.menu_module_usage_logs",
    )

    def _user_tz(self):
        tz_name = request.env.user.tz or request.env.company.partner_id.tz or "UTC"
        return pytz.timezone(tz_name)

    def _local_bounds_to_utc(self, start_date, end_date):
        user_tz = self._user_tz()
        start = user_tz.localize(datetime.combine(start_date, time.min)).astimezone(pytz.utc)
        end = user_tz.localize(datetime.combine(end_date, time.max)).astimezone(pytz.utc)
        return (
            fields.Datetime.to_string(start.replace(tzinfo=None)),
            fields.Datetime.to_string(end.replace(tzinfo=None)),
        )

    def _period_domain(self, period, from_date=None, to_date=None):
        today = datetime.now(self._user_tz()).date()
        if period == "today":
            start_date = end_date = today
        elif period == "week":
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif period == "month":
            start_date = today.replace(day=1)
            end_date = today
        elif period == "custom" and from_date and to_date:
            start_date = fields.Date.from_string(from_date)
            end_date = fields.Date.from_string(to_date)
            if start_date > end_date:
                start_date, end_date = end_date, start_date
        elif period == "all":
            return [], "All Time"
        else:
            start_date = end_date = today

        start_utc, end_utc = self._local_bounds_to_utc(start_date, end_date)
        label = start_date.strftime("%d %b %Y")
        if start_date != end_date:
            label = "%s - %s" % (start_date.strftime("%d %b %Y"), end_date.strftime("%d %b %Y"))
        return [("start_datetime", ">=", start_utc), ("start_datetime", "<=", end_utc)], label

    @http.route(
        "/module_usage_tracker/ping",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def ping(self, module_name=None, module_xmlid=None, menu_id=None, action_id=None, tab_uuid=None, duration_seconds=0):
        env = request.env
        duration = int(duration_seconds or 0)
        if duration <= 0:
            return {"ok": True, "stored": False}

        # Keep one browser heartbeat from inflating data after suspended tabs or sleep.
        duration = min(duration, 300)
        module_name = (module_name or "Unknown").strip()[:128]
        module_xmlid = (module_xmlid or "").strip()[:255]
        if module_name in self._excluded_module_names or module_xmlid in self._excluded_module_xmlids:
            return {"ok": True, "stored": False}
        action_id = str(action_id or "")[:128]
        tab_uuid = (tab_uuid or "").strip()[:64]

        end_dt = fields.Datetime.now()
        start_dt = end_dt - timedelta(seconds=duration)
        env["module.usage.log"].sudo().create({
            "user_id": env.user.id,
            "company_id": env.company.id,
            "module_name": module_name,
            "module_xmlid": module_xmlid,
            "menu_id": int(menu_id or 0),
            "action_id": action_id,
            "tab_uuid": tab_uuid,
            "start_datetime": fields.Datetime.to_string(start_dt),
            "end_datetime": fields.Datetime.to_string(end_dt),
            "duration_seconds": duration,
        })
        return {"ok": True, "stored": True}

    @http.route(
        "/module_usage_tracker/dashboard_data",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def dashboard_data(self, period="today", from_date=None, to_date=None, user_id=None):
        env = request.env
        Log = env["module.usage.log"].sudo()
        domain, label = self._period_domain(period, from_date, to_date)
        domain.append(("company_id", "=", env.company.id))
        domain.extend([
            ("module_name", "not in", list(self._excluded_module_names)),
            ("module_xmlid", "not in", list(self._excluded_module_xmlids)),
        ])
        if user_id:
            domain.append(("user_id", "=", int(user_id)))

        grouped = Log.read_group(domain, ["duration_seconds:sum"], ["module_name"])
        grouped = sorted(grouped, key=lambda item: item.get("duration_seconds", 0) or 0, reverse=True)
        total_seconds = sum(item.get("duration_seconds", 0) or 0 for item in grouped)
        rows = []
        for item in grouped:
            seconds = int(item.get("duration_seconds", 0) or 0)
            percentage = round((seconds / total_seconds) * 100, 2) if total_seconds else 0
            rows.append({
                "module_name": item.get("module_name") or "Unknown",
                "seconds": seconds,
                "duration": Log._format_duration(seconds),
                "percentage": percentage,
                "domain": item.get("__domain", []),
            })

        user_groups = Log.read_group(domain, ["duration_seconds:sum"], ["user_id"])
        user_groups = sorted(user_groups, key=lambda item: item.get("duration_seconds", 0) or 0, reverse=True)[:8]
        users = [{
            "id": group["user_id"][0] if group.get("user_id") else False,
            "name": group["user_id"][1] if group.get("user_id") else "Unknown",
            "seconds": int(group.get("duration_seconds", 0) or 0),
            "duration": Log._format_duration(group.get("duration_seconds", 0) or 0),
        } for group in user_groups]

        recent = Log.search_read(
            domain,
            ["user_id", "module_name", "start_datetime", "duration_seconds", "duration_display"],
            order="start_datetime desc",
            limit=12,
        )

        trend_domain = list(domain)
        if period == "all":
            start_date = datetime.now(self._user_tz()).date() - timedelta(days=13)
            start_utc, _ = self._local_bounds_to_utc(start_date, datetime.now(self._user_tz()).date())
            trend_domain.append(("start_datetime", ">=", start_utc))
        trend_records = Log.search_read(trend_domain, ["start_datetime", "duration_seconds"], limit=5000)
        daily = defaultdict(int)
        user_tz = self._user_tz()
        for record in trend_records:
            start = fields.Datetime.from_string(record["start_datetime"])
            local_day = pytz.utc.localize(start).astimezone(user_tz).date().strftime("%d %b")
            daily[local_day] += record["duration_seconds"] or 0
        trend = [{"label": day, "hours": round(seconds / 3600, 2)} for day, seconds in sorted(daily.items())]

        return {
            "label": label,
            "total_seconds": total_seconds,
            "total_duration": Log._format_duration(total_seconds),
            "module_count": len(rows),
            "top_module": rows[0]["module_name"] if rows else "-",
            "rows": rows,
            "users": users,
            "recent": recent,
            "trend": trend[-14:],
            "last_refresh": datetime.now(user_tz).strftime("%I:%M:%S %p"),
        }
