import base64
import io
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from reportlab.pdfgen import canvas

import main


class PdfGenerationTests(unittest.TestCase):
    def setUp(self):
        self.previous_cache_dir = main.CACHE_DIR
        self.temp_dir = tempfile.TemporaryDirectory()
        main.CACHE_DIR = self.temp_dir.name
        main.app.config['TESTING'] = True
        self.client = main.app.test_client()

        image_buffer = io.BytesIO()
        Image.new('RGB', (400, 600), 'white').save(image_buffer, format='PNG')
        self.image_data = image_buffer.getvalue()

    def tearDown(self):
        main.CACHE_DIR = self.previous_cache_dir
        self.temp_dir.cleanup()

    def test_generates_pdf_from_cache_ids(self):
        cache_id = 'a' * 32
        with open(os.path.join(main.CACHE_DIR, f'{cache_id}.png'), 'wb') as image_file:
            image_file.write(self.image_data)

        response = self.client.post(
            '/generate-pdf-from-labels',
            json={'labels': [{'cache_id': cache_id}]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/pdf')
        self.assertTrue(response.data.startswith(b'%PDF-'))

    def test_accepts_legacy_base64_image_payload(self):
        response = self.client.post(
            '/generate-pdf-from-labels',
            json={
                'labels': [{
                    'image': base64.b64encode(self.image_data).decode('ascii'),
                }],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'%PDF-'))

    def test_reports_expired_cached_label(self):
        response = self.client.post(
            '/generate-pdf-from-labels',
            json={'labels': [{'cache_id': 'b' * 32}]},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn('no longer in the server cache', response.get_json()['error'])

    def test_rejects_invalid_cache_id(self):
        response = self.client.post(
            '/generate-pdf-from-labels',
            json={'labels': [{'cache_id': '../not-safe'}]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('invalid cache ID', response.get_json()['error'])

    def test_pdf_import_uses_bounded_labelary_request_and_returns_cache_id(self):
        source_pdf = io.BytesIO()
        pdf_canvas = canvas.Canvas(source_pdf)
        pdf_canvas.drawString(20, 800, '^XA^FO20,20^FDTest^FS^XZ')
        pdf_canvas.save()
        source_pdf.seek(0)

        labelary_response = Mock(status_code=200, content=self.image_data)
        with patch.object(main.session, 'post', return_value=labelary_response) as post:
            response = self.client.post(
                '/extract-zpl-from-pdf',
                data={'file': (source_pdf, 'labels.pdf')},
                content_type='multipart/form-data',
            )

        self.assertEqual(response.status_code, 200)
        labels = response.get_json()['labels']
        self.assertEqual(len(labels), 1)
        self.assertRegex(labels[0]['cache_id'], r'^[0-9a-f]{32}$')
        self.assertEqual(post.call_args.kwargs['timeout'], main.LABELARY_TIMEOUT)


if __name__ == '__main__':
    unittest.main()
