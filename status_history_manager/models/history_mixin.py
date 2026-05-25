# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class HistoryTrackingMixin(models.AbstractModel):
    """
    Abstract mixin that provides shared utility methods for
    capturing field change history across all tracked models.
    """
    _name = 'history.tracking.mixin'
    _description = 'History Tracking Mixin'


    def _history_get_display_value(self, field_name, value):
        """
        Convert a raw field value to a human-readable string.
        Handles selection labels, Many2one names, floats, and other types.
        """
        if value is None or value is False:
            return ''
        try:
            field = self._fields.get(field_name)
            if not field:
                return str(value)

            if field.type == 'selection':
                selection = field.selection
                if callable(selection):
                    try:
                        selection = field.get_description(self.env).get('selection', [])
                    except Exception:
                        selection = []
                return dict(selection).get(value, str(value))

            elif field.type == 'many2one':
                return value.display_name if value else ''

            elif field.type in ('float', 'monetary'):
                return f'{value:,.4f}'.rstrip('0').rstrip('.')

            elif field.type == 'integer':
                return str(int(value))

            else:
                return str(value)
        except Exception as e:
            _logger.warning('_history_get_display_value error on %s.%s: %s', self._name, field_name, e)
            return str(value)


    def _history_get_employee(self):
        """
        Returns the hr.employee linked to the current user (if any).
        Also returns the stored name for future-safe logging.
        """
        user = self.env.user
        employee = self.env['hr.employee'].search(
            [('user_id', '=', user.id)], limit=1
        )
        employee_name = employee.name if employee else user.name or ''
        return user, employee, employee_name


    def _history_capture_old_values(self, vals, tracked_fields):
        """
        Capture current field values for all records in self BEFORE write.
        tracked_fields = {'field_name': ('Label', 'change_type')}

        Returns dict: {record_id: {field_name: (display_value, raw_value)}}
        """
        old_values = {}
        fields_to_capture = [f for f in tracked_fields if f in vals]
        if not fields_to_capture:
            return old_values

        for record in self:
            old_values[record.id] = {}
            for field_name in fields_to_capture:
                raw = record[field_name]
                display = self._history_get_display_value(field_name, raw)
                old_values[record.id][field_name] = (display, raw)

        return old_values


    def _history_build_logs(
        self,
        old_values,
        vals,
        tracked_fields,
        parent_field,
        parent_id_getter,
        product_getter=None,
    ):
        """
        Compare old vs new values and return list of log dicts to create.

        :param old_values: result of _history_capture_old_values
        :param vals: the vals dict passed to write()
        :param tracked_fields: {'field_name': ('Label', 'change_type')}
        :param parent_field: the Many2one field name on status.history.log
                             e.g. 'purchase_order_id'
        :param parent_id_getter: callable(record) → integer id of parent document
        :param product_getter: callable(record) → (product_id, product_name) or None
        """
        if not old_values:
            return []

        user, employee, employee_name = self._history_get_employee()
        now = fields.Datetime.now()
        logs = []

        for record in self:
            if record.id not in old_values:
                continue

            parent_id = parent_id_getter(record)
            if not parent_id:
                continue

            product_id = False
            product_name = ''
            if product_getter:
                try:
                    product_id, product_name = product_getter(record)
                except Exception:
                    pass

            for field_name, (label, change_type) in tracked_fields.items():
                if field_name not in vals:
                    continue
                if field_name not in old_values.get(record.id, {}):
                    continue

                old_display, old_raw = old_values[record.id][field_name]
                new_display = self._history_get_display_value(field_name, record[field_name])

                # Only log if value actually changed
                if old_display == new_display:
                    continue

                logs.append({
                    'date': now,
                    'user_id': user.id,
                    'employee_id': employee.id if employee else False,
                    'employee_name': employee_name,
                    'field_label': label,
                    'change_type': change_type,
                    'value_from': old_display,
                    'value_to': new_display,
                    'product_id': product_id,
                    'product_name': product_name,
                    parent_field: parent_id,
                })

        return logs


    def _history_create_logs(self, logs):
        """Create log records, skipping re-entrant tracking via context."""
        if logs:
            self.env['status.history.log'].with_context(
                skip_history_log=True
            ).create(logs)
