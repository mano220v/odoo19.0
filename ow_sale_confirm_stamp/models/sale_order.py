# -*- coding: utf-8 -*-

from html import escape

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    ow_confirmed_at = fields.Datetime(
        string='Confirmed On',
        readonly=True,
        copy=False,
    )
    ow_confirmed_date_label = fields.Char(
        string='Confirmed Date',
        compute='_compute_ow_confirmed_date_label',
    )
    ow_stamp_company_name = fields.Char(
        string='Stamp Company Name',
        compute='_compute_ow_stamp_company_name',
    )
    ow_stamp_svg = fields.Html(
        string='Confirmation Stamp',
        compute='_compute_ow_stamp_svg',
        sanitize=False,
    )

    @api.depends('ow_confirmed_at', 'date_order', 'state')
    def _compute_ow_confirmed_date_label(self):
        for order in self:
            confirmed_at = order.ow_confirmed_at
            if not confirmed_at and order.state in ('sale', 'done'):
                confirmed_at = order.date_order
            if confirmed_at:
                confirmed_at = fields.Datetime.context_timestamp(order, confirmed_at)
                order.ow_confirmed_date_label = confirmed_at.strftime('%d %b %Y')
            else:
                order.ow_confirmed_date_label = ''

    @api.depends('company_id')
    def _compute_ow_stamp_company_name(self):
        for order in self:
            order.ow_stamp_company_name = order.company_id.name or self.env.company.name or ''

    @api.depends('ow_stamp_company_name', 'ow_confirmed_date_label')
    def _compute_ow_stamp_svg(self):
        for order in self:
            company_name = escape((order.ow_stamp_company_name or 'COMPANY NAME').upper())
            confirmed_date = escape(order.ow_confirmed_date_label or '')
            order.ow_stamp_svg = f'''
<svg class="ow_sale_confirm_stamp_svg" viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Sale confirmed stamp">
    <defs>
        <path id="ow_stamp_top_{order.id or 'new'}" d="M 20 80 A 60 60 0 0 1 140 80"/>
    </defs>
    <circle cx="80" cy="80" r="71" class="ow_stamp_outer"/>
    <circle cx="80" cy="80" r="54" class="ow_stamp_dash"/>
    <circle cx="80" cy="80" r="38" class="ow_stamp_inner"/>
    <text class="ow_stamp_company">
        <textPath href="#ow_stamp_top_{order.id or 'new'}" startOffset="50%" text-anchor="middle">{company_name}</textPath>
    </text>
    <text x="80" y="73" class="ow_stamp_main" text-anchor="middle">SALE</text>
    <text x="80" y="91" class="ow_stamp_main ow_stamp_confirmed" text-anchor="middle">CONFIRMED</text>
    <line x1="50" y1="101" x2="110" y2="101" class="ow_stamp_line"/>
    <text x="80" y="118" class="ow_stamp_date" text-anchor="middle">{confirmed_date}</text>
</svg>'''

    def action_confirm(self):
        result = super().action_confirm()
        now = fields.Datetime.now()
        for order in self.filtered(lambda rec: rec.state in ('sale', 'done') and not rec.ow_confirmed_at):
            order.ow_confirmed_at = now
        return result
