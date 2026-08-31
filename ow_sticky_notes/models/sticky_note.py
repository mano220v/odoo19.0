# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OwStickyNote(models.Model):
    _name = 'ow.sticky.note'
    _description = 'Sticky Note'
    _order = 'is_pinned desc, sequence asc, write_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Title', default='Untitled')
    content = fields.Text(string='Content')
    color = fields.Selection(
        selection=[
            ('yellow', 'Yellow'),
            ('pink', 'Pink'),
            ('blue', 'Blue'),
            ('green', 'Green'),
            ('purple', 'Purple'),
            ('orange', 'Orange'),
        ],
        string='Color',
        default='yellow',
        required=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    is_pinned = fields.Boolean(string='Pinned')
    user_id = fields.Many2one(
        'res.users',
        string='Owner',
        default=lambda self: self.env.user,
        required=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    # Optional link to whatever record the note was created from, so it
    # can resurface when the user is back on that record.
    res_model = fields.Char(string='Linked Model', index=True)
    res_id = fields.Integer(string='Linked Record ID', index=True)
    res_name = fields.Char(string='Linked Record Name')

    @api.model_create_multi
    def create(self, vals_list):
        # Always force ownership to the current user regardless of what
        # the client sends — these are private notes.
        for vals in vals_list:
            vals['user_id'] = self.env.uid
        return super().create(vals_list)
