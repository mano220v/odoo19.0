# Word Editor for Odoo 19

Word Editor adds an in-Odoo document processor for creating, formatting, saving, sharing, printing, and exporting business documents.

## Compatibility

- Odoo 19.0 Community and Enterprise
- Requires `base`, `web`, and `mail`
- Optional for native DOCX export: `python-docx` and `beautifulsoup4`

## Installation

1. Copy the `word_editor` folder into an Odoo addons path.
2. Restart the Odoo server.
3. Update the Apps list.
4. Install **Word Editor - Document Processor**.
5. Assign access from **Settings > Users > Access Rights > Word Editor**:
   - **User**: create and manage own documents, read shared documents.
   - **Manager**: manage all documents, templates, tags, and categories.

For native Microsoft Word export, install the optional server libraries:

```bash
pip install python-docx beautifulsoup4
```

If those libraries are not installed, DOCX export falls back to an HTML download. PDF export still works through Odoo reports.

## How to Use

1. Open **Word Editor > My Documents**.
2. Click **New Document** or open an existing document.
3. Use the toolbar to format text, insert tables, links, images, horizontal rules, and page breaks.
4. The editor auto-saves changes every few seconds. Use **Save** or `Ctrl + S` before closing when you want an immediate save.
5. Use **Templates** inside the editor to start from a built-in template.
6. Use **DOCX**, **PDF**, or **Print** from the editor header to export the document.

## Document Management

The document form lets you manage metadata outside the full editor:

- Title
- Author
- Category
- Tags
- Status: Draft, In Review, Published, Archived
- Shared URL
- Chatter messages and activities

To share a read-only public page, enable **Shared** on the document form and copy the **Share URL**.

## Templates

Managers can maintain templates from **Word Editor > Templates**. A template stores reusable HTML content and can be selected from the editor's **Templates** button.

Built-in templates:

- Blank Document
- Business Letter
- Meeting Notes
- Project Report
- Invoice / Quote

## Configuration

Managers can configure:

- **Tags** from **Word Editor > Configuration > Tags**
- **Categories** from **Word Editor > Configuration > Categories**
- **Templates** from **Word Editor > Templates**

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl + B` | Bold |
| `Ctrl + I` | Italic |
| `Ctrl + U` | Underline |
| `Ctrl + S` | Save |
| `Ctrl + Z` | Undo |
| `Ctrl + Y` | Redo |
| `Ctrl + A` | Select all |
| `Ctrl + K` | Insert link |
| `Ctrl + F` | Find and replace |
| `Tab` | Insert four spaces |

## Troubleshooting

- **DOCX downloads as HTML**: install `python-docx` and `beautifulsoup4`, then restart Odoo.
- **PDF export fails**: confirm your Odoo PDF/report engine is configured correctly.
- **Users cannot see the menu**: assign the Word Editor User or Manager group.
- **A user cannot edit a shared document**: this is expected. Shared documents are read-only for regular users unless they are the author or a manager.

