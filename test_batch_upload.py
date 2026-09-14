import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

from backend.batch_upload import ingest_uploaded_directory
from backend.services import AppServices


class BatchUploadTest(unittest.TestCase):
    def test_directory_scan_import_and_html_assets(self):
        service = AppServices.__new__(AppServices)
        service.kb = Mock()
        service.kb.upload_documents.return_value = '[成功] 1 chunks'
        service.loader = Mock()
        def files():
            return [SimpleNamespace(filename=name, file=io.BytesIO(data)) for name, data in [
                ('docs/a/page.html', b'<html><body>Test document</body></html>'),
                ('docs/index.html', b'<html>Navigation</html>'),
                ('docs/a/style.css', b'body { color: blue; }')]]
        with tempfile.TemporaryDirectory() as directory, patch('config_data.PROJECT_ROOT', Path(directory)):
            result = ingest_uploaded_directory(service, files(), False, True, 'tester')
            self.assertEqual(result['kept_files'], 1)
            self.assertEqual(result['skipped_noise_html'], 1)
            service.kb.upload_documents.assert_not_called()
            self.assertEqual(list((Path(directory) / 'uploads' / 'batches').iterdir()), [])
            result = ingest_uploaded_directory(service, files(), False, False, 'tester')
            self.assertEqual(result['success_count'], 1)
            self.assertEqual(result['failed_count'], 0)
            source = service.kb.upload_documents.call_args.kwargs['filename']
            self.assertTrue(service.html_source_asset(source).exists())
            css = source.replace('page.html', 'style.css')
            self.assertIn('color: blue', service.html_source_asset(css).read_text())
            service.kb.upload_documents.return_value = '[跳过] duplicate'
            result = ingest_uploaded_directory(service, files(), False, False, 'tester')
            self.assertEqual(result['skipped_count'], 1)
            service.kb.upload_documents.side_effect = [RuntimeError('test failure'), '[成功] 1 chunks']
            result = ingest_uploaded_directory(service, files(), True, False, 'tester')
            self.assertEqual(result['failed_count'], 1)
            self.assertEqual(result['success_count'], 1)
            self.assertEqual(len(result['failures']), 1)

    def test_rejects_path_escape_and_duplicate_paths(self):
        for names in [['../escape.txt'], ['C:/escape.txt'], ['/escape.txt'], ['docs/a.txt', 'docs/A.txt']]:
            with self.subTest(names=names), tempfile.TemporaryDirectory() as directory, patch('config_data.PROJECT_ROOT', Path(directory)):
                files = [SimpleNamespace(filename=name, file=io.BytesIO(b'test')) for name in names]
                service = Mock()
                with self.assertRaises(ValueError):
                    ingest_uploaded_directory(service, files, False, False, 'tester')
                service.batch_ingest.assert_not_called()


if __name__ == '__main__':
    unittest.main()
