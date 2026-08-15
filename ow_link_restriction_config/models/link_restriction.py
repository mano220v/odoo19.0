from odoo import fields, models


class OwLinkRestriction(models.Model):
    _name = 'ow.link.restriction'
    _description = 'Internal Link Restriction Config'
    _rec_name = 'model_id'

    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        help='Model whose Many2one fields should lose the "open linked '
             'record" click-through, on this model\'s Form and List '
             'views. Kanban views are never affected.',
    )
    model_name = fields.Char(
        string='Technical Name',
        related='model_id.model',
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Untick to stop restricting this model without deleting '
             'the entry. Requires a browser refresh to take effect.',
    )
    note = fields.Char(string='Note')

    _sql_constraints = [
        (
            'model_uniq',
            'unique(model_id)',
            'This model is already in the restriction list.',
        ),
    ]
