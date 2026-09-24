# PDF & Word Converter Pro

Offline document conversion for Odoo 19.

- PDF to DOCX with `pdf2docx` when available
- Built-in editable-text DOCX fallback using `pypdf` and `python-docx`
- DOC/DOCX to PDF through headless LibreOffice
- Per-user history, 25 MB validation, secure temporary directories, conversion timeout, and automatic output cleanup

## Server requirements

Install LibreOffice for Word-to-PDF. Install `pdf2docx` for enhanced PDF layout reconstruction. Without `pdf2docx`, PDF-to-DOCX remains available in text-extraction mode. Scanned PDFs require OCR before conversion.
