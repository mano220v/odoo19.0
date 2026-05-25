# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

# ── Fields tracked via write() (non-computed) ─────────────────────────────────
PICKING_TRACKED = {}  # state is computed, handled via action overrides below

MOVE_TRACKED = {
    'product_uom_qty': ('Demand Quantity', 'quantity'),
    'quantity':        ('Done Quantity',   'quantity'),
}

# Human-readable labels for stock.picking state values
PICKING_STATE_LABELS = {
    'draft':           'Draft',
    'waiting':         'Waiting',
    'confirmed':       'Confirmed',
    'assigned':        'Ready',
    'done':            'Done',
    'cancel':          'Cancelled',
}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    history_log_ids = fields.One2many(
        comodel_name='status.history.log',
        inverse_name='stock_picking_id',
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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _history_state_label(self, state_key):
        """Convert a raw state key to a display label."""
        return PICKING_STATE_LABELS.get(state_key, state_key or '')

    def _history_get_employee(self):
        user = self.env.user
        employee = self.env['hr.employee'].search(
            [('user_id', '=', user.id)], limit=1)
        return user, employee, employee.name if employee else (user.name or '')

    def _history_create_logs(self, logs):
        if logs:
            self.env['status.history.log'].with_context(
                skip_history_log=True
            ).create(logs)

    def _history_log_state_change(self, old_states):
        """
        Compare old_states {record.id: label} against current state
        and create a history log for every picking whose state changed.
        Call this AFTER super() has run.
        """
        if not old_states:
            return
        user, employee, emp_name = self._history_get_employee()
        now = fields.Datetime.now()
        logs = []
        for record in self:
            old_label = old_states.get(record.id, '')
            new_label = self._history_state_label(record.state)
            if old_label == new_label:
                continue
            logs.append({
                'date':             now,
                'user_id':          user.id,
                'employee_id':      employee.id if employee else False,
                'employee_name':    emp_name,
                'field_label':      'Status',
                'change_type':      'state',
                'value_from':       old_label,
                'value_to':         new_label,
                'stock_picking_id': record.id,
                'note':             record.name,
            })
        self._history_create_logs(logs)

    def _capture_old_states(self):
        """Snapshot current state labels for all records in self."""
        return {r.id: self._history_state_label(r.state) for r in self}

    # ── Action overrides — every state transition goes through one of these ───

    def action_confirm(self):
        old_states = self._capture_old_states()
        result = super().action_confirm()
        self._history_log_state_change(old_states)
        return result

    def action_assign(self):
        old_states = self._capture_old_states()
        result = super().action_assign()
        self._history_log_state_change(old_states)
        return result

    def button_validate(self):
        old_states = self._capture_old_states()
        result = super().button_validate()
        # button_validate may return a wizard action instead of completing
        # immediately; refresh self to pick up the final state.
        self._history_log_state_change(old_states)
        return result

    def action_cancel(self):
        old_states = self._capture_old_states()
        result = super().action_cancel()
        self._history_log_state_change(old_states)
        return result

    def do_unreserve(self):
        old_states = self._capture_old_states()
        result = super().do_unreserve()
        self._history_log_state_change(old_states)
        return result

    # ── write() still handles any non-computed field changes ─────────────────

    def write(self, vals):
        if self.env.context.get('skip_history_log'):
            return super().write(vals)

        # state is computed — skip it here; it is handled by action overrides
        non_state_tracked = {k: v for k, v in PICKING_TRACKED.items()
                             if k in vals and k != 'state'}

        old_values = {}
        if non_state_tracked:
            for record in self:
                old_values[record.id] = {
                    fn: self._history_get_display_value(fn, record[fn])
                    for fn in non_state_tracked
                }

        result = super().write(vals)

        if old_values:
            user, employee, emp_name = self._history_get_employee()
            now = fields.Datetime.now()
            logs = []
            for record in self:
                if record.id not in old_values:
                    continue
                for fn, (label, ctype) in non_state_tracked.items():
                    old_d = old_values[record.id].get(fn, '')
                    new_d = self._history_get_display_value(fn, record[fn])
                    if old_d == new_d:
                        continue
                    logs.append({
                        'date':             now,
                        'user_id':          user.id,
                        'employee_id':      employee.id if employee else False,
                        'employee_name':    emp_name,
                        'field_label':      label,
                        'change_type':      ctype,
                        'value_from':       old_d,
                        'value_to':         new_d,
                        'stock_picking_id': record.id,
                        'note':             record.name,
                    })
            self._history_create_logs(logs)

        return result

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


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _history_get_display_value(self, field_name, value):
        if value is None or value is False:
            return ''
        try:
            field = self._fields.get(field_name)
            if not field:
                return str(value)
            if field.type in ('float', 'monetary'):
                return f'{value:,.4f}'.rstrip('0').rstrip('.') or '0'
            else:
                return str(value)
        except Exception:
            return str(value)

    def _history_get_employee(self):
        user = self.env.user
        employee = self.env['hr.employee'].search(
            [('user_id', '=', user.id)], limit=1)
        return user, employee, employee.name if employee else (user.name or '')

    def _history_create_logs(self, logs):
        if logs:
            self.env['status.history.log'].with_context(
                skip_history_log=True
            ).create(logs)

    def write(self, vals):
        if self.env.context.get('skip_history_log'):
            return super().write(vals)

        old_values = {}
        fields_changing = [f for f in MOVE_TRACKED if f in vals]
        if fields_changing:
            for record in self:
                old_values[record.id] = {
                    fn: self._history_get_display_value(fn, record[fn])
                    for fn in fields_changing
                }

        result = super().write(vals)

        if old_values:
            user, employee, emp_name = self._history_get_employee()
            now = fields.Datetime.now()
            logs = []
            for record in self:
                if record.id not in old_values:
                    continue
                picking = record.picking_id
                if not picking:
                    continue
                for fn, (label, ctype) in MOVE_TRACKED.items():
                    if fn not in vals:
                        continue
                    old_d = old_values[record.id].get(fn, '')
                    new_d = self._history_get_display_value(fn, record[fn])
                    if old_d == new_d:
                        continue
                    product = record.product_id
                    logs.append({
                        'date':             now,
                        'user_id':          user.id,
                        'employee_id':      employee.id if employee else False,
                        'employee_name':    emp_name,
                        'field_label':      label,
                        'change_type':      ctype,
                        'value_from':       old_d,
                        'value_to':         new_d,
                        'product_id':       product.id if product else False,
                        'product_name':     product.display_name if product else '',
                        'stock_picking_id': picking.id,
                        'note':             picking.name,
                    })
            self._history_create_logs(logs)

        return result
