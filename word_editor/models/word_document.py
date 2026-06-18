# -*- coding: utf-8 -*-
import re
import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)


class WordDocument(models.Model):
    _name = 'word.document'
    _description = 'Word Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'write_date desc'

    # ─── Core Fields ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Title',
        required=True,
        default='Untitled Document',
        tracking=True,
        index=True,
    )
    content = fields.Html(
        string='Content',
        sanitize=False,
        translate=False,
    )
    author_id = fields.Many2one(
        'res.users',
        string='Author',
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    # ─── Categorisation ───────────────────────────────────────────────────────
    tag_ids = fields.Many2many(
        'word.document.tag',
        string='Tags',
    )
    category_id = fields.Many2one(
        'word.document.category',
        string='Category',
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'In Review'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', tracking=True, index=True)

    # ─── Statistics (computed) ────────────────────────────────────────────────
    word_count = fields.Integer(
        string='Words',
        compute='_compute_stats',
        store=True,
    )
    char_count = fields.Integer(
        string='Characters',
        compute='_compute_stats',
        store=True,
    )
    reading_time = fields.Integer(
        string='Reading Time (min)',
        compute='_compute_stats',
        store=True,
        help='Estimated reading time at 200 words per minute',
    )
    page_count = fields.Integer(
        string='Estimated Pages',
        compute='_compute_stats',
        store=True,
    )

    # ─── Sharing ──────────────────────────────────────────────────────────────
    is_shared = fields.Boolean(string='Shared', default=False, tracking=True)
    share_url = fields.Char(string='Share URL', compute='_compute_share_url')

    # ─── Template ─────────────────────────────────────────────────────────────
    template_id = fields.Many2one(
        'word.document.template',
        string='Based on Template',
    )
    is_template = fields.Boolean(string='Is Template', default=False)

    # ─── Attachments ──────────────────────────────────────────────────────────
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Onchange Methods
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """
        When a template is selected in the form view, copy its HTML content
        into this document so the Document Preview tab renders immediately.
        Clears the content field if the template is removed.
        """
        if self.template_id:
            self.content = self.template_id.content
        # If user clears the template field, leave existing content untouched
        # (don't blank it — they may have already typed something).

    # ─────────────────────────────────────────────────────────────────────────
    # Computed Methods
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('content')
    def _compute_stats(self):
        for rec in self:
            if rec.content:
                text = re.sub(r'<[^>]+>', ' ', rec.content)
                text = re.sub(r'\s+', ' ', text).strip()
                words = [w for w in text.split(' ') if w]
                wc = len(words)
                cc = sum(len(w) for w in words)
                rec.word_count = wc
                rec.char_count = cc
                rec.reading_time = max(1, round(wc / 200))
                rec.page_count = max(1, round(wc / 300))
            else:
                rec.word_count = 0
                rec.char_count = 0
                rec.reading_time = 0
                rec.page_count = 0

    @api.depends('is_shared')
    def _compute_share_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for rec in self:
            if rec.is_shared and rec.id:
                rec.share_url = f'{base}/word_editor/view/{rec.id}'
            else:
                rec.share_url = False

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', self._name),
                ('res_id', '=', rec.id),
            ])

    # ─────────────────────────────────────────────────────────────────────────
    # Action Methods
    # ─────────────────────────────────────────────────────────────────────────

    def action_open_editor(self):
        """Open document in the full-screen Word Editor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'word_editor_action',
            'name': self.name,
            'params': {
                'doc_id': self.id,
                'doc_name': self.name,
            },
        }

    def action_new_document(self):
        """Open the editor to create a new blank document."""
        return {
            'type': 'ir.actions.client',
            'tag': 'word_editor_action',
            'name': _('New Document'),
            'params': {},
        }

    def action_export_docx(self):
        """Download the document as a .docx file."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/word_editor/export/docx/{self.id}',
            'target': 'self',
        }

    def action_export_pdf(self):
        """Download the document as a .pdf file."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/word_editor/export/pdf/{self.id}',
            'target': 'new',
        }

    def action_publish(self):
        self.write({'state': 'published'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_set_review(self):
        self.write({'state': 'review'})

    def action_archive_doc(self):
        self.write({'state': 'archived'})

    def action_duplicate(self):
        """Duplicate this document."""
        self.ensure_one()
        new_doc = self.copy({'name': _('%s (Copy)') % self.name})
        return new_doc.action_open_editor()

    def action_view_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attachments'),
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
        }

    def action_create_from_template(self):
        """Create a new document from this template."""
        self.ensure_one()
        if not self.is_template:
            raise UserError(_('This document is not a template.'))
        new_doc = self.env['word.document'].create({
            'name': _('Document from %s') % self.name,
            'content': self.content,
            'template_id': False,
        })
        return new_doc.action_open_editor()


class WordDocumentTag(models.Model):
    _name = 'word.document.tag'
    _description = 'Word Document Tag'
    _order = 'name'

    name = fields.Char(string='Tag', required=True, index=True)
    color = fields.Integer(string='Color Index', default=0)
    document_count = fields.Integer(
        string='Documents',
        compute='_compute_document_count',
    )

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        'Tag name must be unique.',
    )

    def _compute_document_count(self):
        for tag in self:
            tag.document_count = self.env['word.document'].search_count([
                ('tag_ids', 'in', tag.id)
            ])


class WordDocumentCategory(models.Model):
    _name = 'word.document.category'
    _description = 'Word Document Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    color = fields.Integer(string='Color Index', default=0)
    parent_id = fields.Many2one('word.document.category', string='Parent Category')
    child_ids = fields.One2many('word.document.category', 'parent_id', string='Sub-categories')
    document_count = fields.Integer(
        string='Documents',
        compute='_compute_document_count',
    )

    def _compute_document_count(self):
        for cat in self:
            cat.document_count = self.env['word.document'].search_count([
                ('category_id', '=', cat.id)
            ])


class WordDocumentTemplate(models.Model):
    _name = 'word.document.template'
    _description = 'Word Document Template'
    _order = 'sequence, name'

    name = fields.Char(string='Template Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    content = fields.Html(string='Template Content', sanitize=False)
    category = fields.Selection([
        ('blank', 'Blank'),
        ('business', 'Business'),
        ('letter', 'Letter / Correspondence'),
        ('report', 'Report'),
        ('meeting', 'Meeting Notes'),
        ('invoice', 'Invoice / Quote'),
        ('resume', 'Resume / CV'),
        ('legal', 'Legal'),
        ('other', 'Other'),
    ], string='Category', default='other', required=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color Index', default=0)
    icon = fields.Char(string='Icon', default='fa-file-text-o')

    def action_create_document(self):
        """Create a new document based on this template."""
        self.ensure_one()
        doc = self.env['word.document'].create({
            'name': _('Document from %s') % self.name,
            'content': self.content or '',
            'template_id': self.id,
        })
        return doc.action_open_editor()
