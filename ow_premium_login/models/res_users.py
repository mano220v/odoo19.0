# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessDenied, ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    login_auth_method = fields.Selection(
        selection=[
            ('password', 'Password'),
            ('pin', 'Quick PIN'),
            ('pattern', 'Unlock pattern'),
            ('text_lock', 'Text lock'),
        ],
        string='Login method',
        default='password',
        required=True,
        copy=False,
        groups='base.group_system',
        help='The credential type shown first on the premium login screen for this user.',
    )
    login_pin_hash = fields.Char(copy=False, groups='base.group_system')
    login_pattern_hash = fields.Char(copy=False, groups='base.group_system')
    login_text_lock_hash = fields.Char(copy=False, groups='base.group_system')

    new_login_pin = fields.Char(
        string='Set PIN',
        compute='_compute_login_secrets',
        inverse='_inverse_login_pin',
        readonly=False,
        copy=False,
        groups='base.group_system',
        help='Use 4 to 8 digits. The value is encrypted and never stored as plain text.',
    )
    new_login_pattern = fields.Char(
        string='Set pattern',
        compute='_compute_login_secrets',
        inverse='_inverse_login_pattern',
        readonly=False,
        copy=False,
        groups='base.group_system',
        help='Enter node numbers in order, for example 0-1-4-7-8. The value is encrypted.',
    )
    new_login_text_lock = fields.Char(
        string='Set text lock',
        compute='_compute_login_secrets',
        inverse='_inverse_login_text_lock',
        readonly=False,
        copy=False,
        groups='base.group_system',
        help='Use a memorable phrase. The value is encrypted and never stored as plain text.',
    )

    @api.depends_context('uid')
    def _compute_login_secrets(self):
        # Never send an existing credential back to the browser or form view.
        for user in self:
            user.new_login_pin = False
            user.new_login_pattern = False
            user.new_login_text_lock = False

    def _hash_login_secret(self, secret):
        return self._crypt_context().hash(secret)

    @staticmethod
    def _normalize_login_pattern(pattern):
        return '-'.join(part.strip() for part in (pattern or '').split('-') if part.strip())

    def _validate_login_secret(self, kind, secret):
        if kind == 'pin' and (not secret.isdigit() or not 4 <= len(secret) <= 8):
            raise ValidationError('The login PIN must contain 4 to 8 digits.')
        if kind == 'pattern':
            nodes = self._normalize_login_pattern(secret).split('-')
            valid_nodes = {str(index) for index in range(9)}
            if len(nodes) < 4 or any(node not in valid_nodes for node in nodes):
                raise ValidationError('The unlock pattern must use at least 4 nodes numbered 0 to 8.')
            if len(set(nodes)) != len(nodes):
                raise ValidationError('An unlock pattern cannot use the same node twice.')
        if kind == 'text_lock' and len(secret.strip()) < 4:
            raise ValidationError('The text lock must contain at least 4 characters.')

    def _inverse_login_pin(self):
        for user in self:
            secret = user.new_login_pin
            if secret:
                user._validate_login_secret('pin', secret)
                user.login_pin_hash = user._hash_login_secret(secret)

    def _inverse_login_pattern(self):
        for user in self:
            secret = user.new_login_pattern
            if secret:
                secret = self._normalize_login_pattern(secret)
                user._validate_login_secret('pattern', secret)
                user.login_pattern_hash = user._hash_login_secret(secret)

    def _inverse_login_text_lock(self):
        for user in self:
            secret = user.new_login_text_lock
            if secret:
                user._validate_login_secret('text_lock', secret)
                user.login_text_lock_hash = user._hash_login_secret(secret)

    def _check_credentials(self, credential, env):
        auth_type = credential.get('type')
        hash_field = {
            'pin': 'login_pin_hash',
            'pattern': 'login_pattern_hash',
            'text_lock': 'login_text_lock_hash',
        }.get(auth_type)
        if not hash_field:
            return super()._check_credentials(credential, env)

        # The method is deliberately user-specific. Selecting PIN in the UI
        # must not turn an unconfigured PIN into a second way around a password.
        if self.login_auth_method != auth_type:
            raise AccessDenied()

        secret = credential.get('password')
        stored_hash = self[hash_field]
        if secret and stored_hash and self._crypt_context().verify(secret, stored_hash):
            return {
                'uid': self.id,
                'auth_method': auth_type,
                'mfa': 'default',
            }
        raise AccessDenied()
