# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StatusHistoryLog(models.Model):
    """
    Central audit log for recording all state, price and quantity changes
    across Purchase Orders, Sales Orders and Stock Pickings.
    """
    _name = 'status.history.log'
    _description = 'Status & Changes History Log'
    _order = 'date desc'
    _rec_name = 'date'


    date = fields.Datetime(
        string='Date & Time',
        default=fields.Datetime.now,
        readonly=True,
        required=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        readonly=True,
        ondelete='set null',
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        readonly=True,
        ondelete='set null',
    )
    employee_name = fields.Char(
        string='Employee Name',
        readonly=True,
        help='Stored name so history is preserved even if employee is deleted',
    )
    field_label = fields.Char(
        string='Changed Field',
        readonly=True,
        required=True,
    )
    change_type = fields.Selection(
        selection=[
            ('state', 'Status'),
            ('price', 'Price'),
            ('quantity', 'Quantity'),
            ('discount', 'Discount'),
            ('other', 'Other'),
        ],
        string='Change Type',
        readonly=True,
        default='other',
    )
    value_from = fields.Char(
        string='From',
        readonly=True,
    )
    value_to = fields.Char(
        string='To',
        readonly=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        readonly=True,
        ondelete='set null',
    )
    product_name = fields.Char(
        string='Product Name',
        readonly=True,
        help='Stored product name for historical reference',
    )
    note = fields.Char(
        string='Reference',
        readonly=True,
    )


    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Purchase Order',
        ondelete='cascade',
        index=True,
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale Order',
        ondelete='cascade',
        index=True,
    )
    stock_picking_id = fields.Many2one(
        comodel_name='stock.picking',
        string='Stock Picking',
        ondelete='cascade',
        index=True,
    )


    @api.depends('employee_id', 'employee_name', 'user_id')
    def _compute_display_employee(self):
        for rec in self:
            if rec.employee_id:
                rec.display_employee = rec.employee_id.name
            elif rec.employee_name:
                rec.display_employee = rec.employee_name
            elif rec.user_id:
                rec.display_employee = rec.user_id.name
            else:
                rec.display_employee = 'Unknown'

    display_employee = fields.Char(
        string='Changed By',
        compute='_compute_display_employee',
        store=False,
    )

    def name_get(self):
        result = []
        for rec in self:
            name = f"[{rec.date}] {rec.field_label}: {rec.value_from} → {rec.value_to}"
            result.append((rec.id, name))
        return result
