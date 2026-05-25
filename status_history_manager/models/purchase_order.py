# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

PURCHASE_ORDER_TRACKED = {
    'state': ('Status', 'state'),
}

PURCHASE_LINE_TRACKED = {
    'price_unit': ('Unit Price', 'price'),
    'product_qty': ('Ordered Quantity', 'quantity'),
}


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    history_log_ids = fields.One2many(
        comodel_name='status.history.log',
        inverse_name='purchase_order_id',
        string='Change History',
        readonly=True,
    )
    history_log_count = fields.Integer(
        string='Changes',
        compute='_compute_history_log_count',
    )

    @api.depends('history_log_ids')
    def _compute_history_log_count(self):
        for rec in self:
            rec.history_log_count = len(rec.history_log_ids)

    def _history_get_display_value(self, field_name, value):
        if value is None or value is False:
            return ''
        try:
            field = self._fields.get(field_name)
            if not field:
                return str(value)
            if field.type == 'selection':
                selection = field.selection
                if callable(selection):
                    selection = field.get_description(self.env).get('selection', [])
                return dict(selection).get(value, str(value))
            elif field.type == 'many2one':
                return value.display_name if value else ''
            elif field.type in ('float', 'monetary'):
                return f'{value:,.4f}'.rstrip('0').rstrip('.') or '0'
            else:
                return str(value)
        except Exception:
            return str(value)

    def _history_get_employee(self):
        user = self.env.user
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        return user, employee, employee.name if employee else (user.name or '')

    def _history_create_logs(self, logs):
        if logs:
            self.env['status.history.log'].with_context(skip_history_log=True).create(logs)

    def write(self, vals):
        if self.env.context.get('skip_history_log'):
            return super().write(vals)

        old_values = {}
        fields_changing = [f for f in PURCHASE_ORDER_TRACKED if f in vals]
        if fields_changing:
            for record in self:
                old_values[record.id] = {}
                for fn in fields_changing:
                    old_values[record.id][fn] = self._history_get_display_value(fn, record[fn])

        result = super().write(vals)

        if old_values:
            user, employee, emp_name = self._history_get_employee()
            now = fields.Datetime.now()
            logs = []
            for record in self:
                if record.id not in old_values:
                    continue
                for fn, (label, ctype) in PURCHASE_ORDER_TRACKED.items():
                    if fn not in vals:
                        continue
                    old_d = old_values[record.id].get(fn, '')
                    new_d = self._history_get_display_value(fn, record[fn])
                    if old_d == new_d:
                        continue
                    logs.append({
                        'date': now,
                        'user_id': user.id,
                        'employee_id': employee.id if employee else False,
                        'employee_name': emp_name,
                        'field_label': label,
                        'change_type': ctype,
                        'value_from': old_d,
                        'value_to': new_d,
                        'purchase_order_id': record.id,
                        'note': record.name,
                    })
            self._history_create_logs(logs)

        return result


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _history_get_display_value(self, field_name, value):
        if value is None or value is False:
            return ''
        try:
            field = self._fields.get(field_name)
            if not field:
                return str(value)
            if field.type == 'selection':
                selection = field.selection
                if callable(selection):
                    selection = field.get_description(self.env).get('selection', [])
                return dict(selection).get(value, str(value))
            elif field.type in ('float', 'monetary'):
                return f'{value:,.4f}'.rstrip('0').rstrip('.') or '0'
            else:
                return str(value)
        except Exception:
            return str(value)

    def _history_get_employee(self):
        user = self.env.user
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        return user, employee, employee.name if employee else (user.name or '')

    def _history_create_logs(self, logs):
        if logs:
            self.env['status.history.log'].with_context(skip_history_log=True).create(logs)

    def write(self, vals):
        if self.env.context.get('skip_history_log'):
            return super().write(vals)

        old_values = {}
        fields_changing = [f for f in PURCHASE_LINE_TRACKED if f in vals]
        if fields_changing:
            for record in self:
                old_values[record.id] = {}
                for fn in fields_changing:
                    old_values[record.id][fn] = self._history_get_display_value(fn, record[fn])

        result = super().write(vals)

        if old_values:
            user, employee, emp_name = self._history_get_employee()
            now = fields.Datetime.now()
            logs = []
            for record in self:
                if record.id not in old_values:
                    continue
                order = record.order_id
                if not order:
                    continue
                for fn, (label, ctype) in PURCHASE_LINE_TRACKED.items():
                    if fn not in vals:
                        continue
                    old_d = old_values[record.id].get(fn, '')
                    new_d = self._history_get_display_value(fn, record[fn])
                    if old_d == new_d:
                        continue
                    product = record.product_id
                    logs.append({
                        'date': now,
                        'user_id': user.id,
                        'employee_id': employee.id if employee else False,
                        'employee_name': emp_name,
                        'field_label': label,
                        'change_type': ctype,
                        'value_from': old_d,
                        'value_to': new_d,
                        'product_id': product.id if product else False,
                        'product_name': product.display_name if product else '',
                        'purchase_order_id': order.id,
                        'note': order.name,
                    })
            self._history_create_logs(logs)

        return result
