from odoo import fields, models


class OwStorageLog(models.Model):
    _name = 'ow.storage.log'
    _description = 'Ow Cache Manager - Cleanup History'
    _order = 'create_date desc'

    action_type = fields.Selection([
        ('asset_cache', 'Asset Cache'),
        ('orphaned', 'Orphaned Junk'),
        ('manual', 'Manual Selection'),
        ('duplicate', 'Duplicate Records'),
    ], required=True, string='Action')
    freed_mb = fields.Float('Freed (MB)')
    cleared_count = fields.Integer('Files Cleared')
