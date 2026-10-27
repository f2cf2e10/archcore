import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'tools'))
from archguard import scan, dot_graph

CATALOG = BASE / 'catalog'
CONTRACT = (BASE / 'examples' / 'generic-hexagonal' / 'architecture.yaml').read_text()

class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'architecture.yaml').write_text(CONTRACT)
        for layer in ('domain', 'application', 'infrastructure'):
            (self.root / 'src' / 'my_package' / layer).mkdir(parents=True)
    def tearDown(self):
        self.temp.cleanup()
    def write(self, layer, name, code):
        p = self.root / 'src' / 'my_package' / layer / name
        p.write_text(code)
    def test_valid_dependency(self):
        self.write('domain', 'model.py', 'class Entity: pass\n')
        self.write('application', 'use_case.py', 'from my_package.domain.model import Entity\n')
        r = scan(self.root, CATALOG)
        self.assertEqual(r['summary']['errors'], 0)
        self.assertEqual(len(r['edges']), 1)
    def test_invalid_dependency(self):
        self.write('infrastructure', 'db.py', 'class DB: pass\n')
        self.write('domain', 'entity.py', 'from my_package.infrastructure.db import DB\n')
        r = scan(self.root, CATALOG)
        self.assertIn('forbidden_layer_dependency', [i['rule'] for i in r['issues']])
    def test_relative_import(self):
        self.write('infrastructure', 'db.py', 'class DB: pass\n')
        self.write('application', 'use_case.py', 'from ..infrastructure.db import DB\n')
        r = scan(self.root, CATALOG)
        self.assertEqual(r['summary']['errors'], 1)
    def test_unclassified_is_reported(self):
        (self.root / 'setup.py').write_text('print(123)')
        r = scan(self.root, CATALOG)
        self.assertEqual(next(f['layer'] for f in r['files'] if f['path']=='setup.py'), 'unclassified')
    def test_missing_directory(self):
        (self.root / 'src' / 'my_package' / 'domain').rmdir()
        r = scan(self.root, CATALOG)
        self.assertIn('missing_layer_directory', [i['rule'] for i in r['issues']])
    def test_dot(self):
        r = scan(self.root, CATALOG)
        self.assertIn('digraph ArchCore', dot_graph(r, 'layers'))
    def test_syntax_errors(self):
        self.write('domain', 'invalid.py', 'class :\n')
        r = scan(self.root, CATALOG)
        self.assertIn('parse_error', [i['rule'] for i in r['issues']])

if __name__ == '__main__':
    unittest.main()
