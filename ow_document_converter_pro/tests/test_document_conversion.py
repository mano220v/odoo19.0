import base64
import io
from docx import Document
from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestDocumentConversion(TransactionCase):

    def test_docx_validation_and_direction(self):
        stream = io.BytesIO()
        document = Document()
        document.add_paragraph('Odoo Wings conversion test')
        document.save(stream)
        conversion = self.env['ow.document.conversion'].create({'name': 'Word test', 'input_filename': 'sample.docx', 'input_file': base64.b64encode(stream.getvalue())})
        self.assertEqual(conversion.direction, 'word_pdf')
        self.assertGreater(conversion.input_size, 0)

    def test_rejects_unsupported_extension(self):
        with self.assertRaises(Exception):
            self.env['ow.document.conversion'].create({'name': 'Invalid', 'input_filename': 'sample.exe', 'input_file': base64.b64encode(b'not a document')})
