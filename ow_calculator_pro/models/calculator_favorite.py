# -*- coding: utf-8 -*-
from odoo import fields, models

from .calculator_history import CALCULATOR_TYPES


class CalculatorFavorite(models.Model):
    _name = "calculator.favorite"
    _description = "Calculator Favorite"
    _order = "sequence, id"

    name = fields.Char(string="Label", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        required=True,
        index=True,
        ondelete="cascade",
    )
    category = fields.Selection(
        CALCULATOR_TYPES,
        string="Calculator Type",
        required=True,
        default="standard",
    )
    expression = fields.Char(string="Expression", required=True)
