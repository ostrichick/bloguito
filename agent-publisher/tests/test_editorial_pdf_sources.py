"""PDF attachments retain source text and fail closed on missing evidence."""
import io
import unittest
from unittest.mock import MagicMock, patch

from agents.editorial_writer import fetch_sources


class PdfSourceTests(unittest.TestCase):
    def test_pdf_octet_stream_without_filename_extension_is_parsed(self):
        page = MagicMock()
        page.extract_text.return_value = 'Reference 2 official banking table\n' + 'Branch information ' * 12
        doc = MagicMock()
        doc.pages = [page]
        resp = MagicMock(status_code=200, content=b'%PDF-1.7 sample attachment')
        brief = {'official_urls': ['https://fsc.go.kr/comm/getFile?fileNo=2'],
                 'entity': '은행'}
        with patch('agents.editorial_writer.requests.get', return_value=resp), \
             patch('pypdf.PdfReader', return_value=doc) as pdf:
            source = fetch_sources(brief)[0]
        self.assertIn('Branch information', source['text'])
        self.assertEqual(source['source_type'], 'official')
        self.assertEqual(source['id'], 's0')
        pdf.assert_called_once()
        self.assertIsInstance(pdf.call_args.args[0], io.BytesIO)
        page.extract_text.assert_called_once_with(extraction_mode='layout')

    def test_unreadable_pdf_cannot_be_cited(self):
        page = MagicMock()
        page.extract_text.return_value = ''
        doc = MagicMock()
        doc.pages = [page]
        resp = MagicMock(status_code=200, content=b'%PDF-1.7 corrupt')
        with patch('agents.editorial_writer.requests.get', return_value=resp), \
             patch('pypdf.PdfReader', return_value=doc):
            with self.assertRaisesRegex(ValueError, 'official_pdf_text_missing'):
                fetch_sources({'official_urls': ['https://fsc.go.kr/comm/getFile'],
                               'entity': '은행'})


if __name__ == '__main__':
    unittest.main()
