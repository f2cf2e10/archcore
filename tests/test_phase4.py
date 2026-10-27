import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'tools'))
from archguard import scan, check_changes, changed_paths
from archcore_contract import validate

CONTRACT = (BASE / 'examples/generic-hexagonal/architecture.yaml').read_text()
CATALOG = BASE / 'catalog'

class EnforcementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'architecture.yaml').write_text(CONTRACT)
        for name in ['domain','application','infrastructure']:
            (self.root/'src/my_package'/name).mkdir(parents=True)
    def tearDown(self):
        self.tmp.cleanup()
    def put(self, layer, file, contents):
        f = self.root/'src/my_package'/layer/file
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(contents)
    def test_framework_import_in_domain(self):
        self.put('domain','model.py','from sqlalchemy.orm import Session\n')
        report=scan(self.root,CATALOG)
        self.assertIn('forbidden_framework_import', [i['rule'] for i in report['issues']])
    def test_framework_import_in_infrastructure_allowed(self):
        self.put('infrastructure','adapter.py','import sqlalchemy\n')
        self.assertEqual(scan(self.root,CATALOG)['summary']['errors'],0)
    def test_transitive_violation(self):
        self.put('domain','a.py','from my_package.application.b import B\n')
        self.put('application','b.py','from my_package.infrastructure.c import C\n')
        self.put('infrastructure','c.py','C = 1\n')
        r=scan(self.root,CATALOG)
        self.assertIn('indirect_layer_dependency',[i['rule'] for i in r['issues']])
    def test_explicit_ports_folder_wrong_layer(self):
        self.put('infrastructure','ports/x.py','X = 1\n')
        r=scan(self.root,CATALOG)
        self.assertIn('misplaced_ports',[i['rule'] for i in r['issues']])
    def test_changed_protected_and_unclassified(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        self.put('domain','entity.py','E = 1\n')
        (self.root/'notes.txt').write_text('test')
        paths=changed_paths(self.root,None)
        self.assertIn('architecture.yaml',paths)
        c,_,_=validate(self.root/'architecture.yaml',CATALOG)
        _,issues=check_changes(self.root,scan(self.root,CATALOG),c)
        self.assertTrue(any(i['file']=='architecture.yaml' for i in issues))
        self.assertTrue(any(i['file']=='src/my_package/domain/entity.py' for i in issues))
        self.assertTrue(any(i['file']=='notes.txt' for i in issues))
    def test_git_absent_fails_closed(self):
        with self.assertRaises(ValueError):
            changed_paths(self.root,None)

if __name__=='__main__': unittest.main()
