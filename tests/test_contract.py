from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import yaml
from tools.archcore_contract import validate

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'catalog'
EXAMPLE = ROOT / 'examples' / 'generic-hexagonal' / 'architecture.yaml'

class ContractTests(unittest.TestCase):
    def check_config(self, config, valid):
        with TemporaryDirectory() as folder:
            target = Path(folder) / 'architecture.yaml'
            target.write_text(yaml.safe_dump(config))
            if valid:
                validate(target, CATALOG)
            else:
                with self.assertRaises(ValueError): validate(target, CATALOG)

    def config(self):
        return yaml.safe_load(EXAMPLE.read_text())

    def test_valid(self): self.check_config(self.config(), True)
    def test_unsupported_contract_metadata_rejected(self):
        c = self.config(); c['archcore'] = {'contract_version': 1}; self.check_config(c, False)
    def test_stable_architecture_id(self):
        c = self.config(); self.assertEqual(c['architecture']['style'], 'hexagonal'); self.check_config(c, True)
    def test_no_ddd_is_valid(self):
        c = self.config(); c['methodologies'] = []; self.check_config(c, True)
    def test_protection_cannot_weaken(self):
        c = self.config(); c['governance']['protection']['domain'] = 'allowed_within_scope'; self.check_config(c, False)
    def test_unclassified_fails_closed(self):
        c = self.config(); c['governance']['unclassified'] = 'allowed_within_scope'; self.check_config(c, False)
    def test_overlapping_paths(self):
        c = self.config(); c['architecture']['layers']['domain'] = 'src/my_package'; self.check_config(c, False)
    def test_protect_contract(self):
        c = self.config(); c['governance']['protected_files'] = []; self.check_config(c, False)
    def test_missing_methodology(self):
        c = self.config(); c['methodologies'] = ['unknown']; self.check_config(c, False)
    def test_patterns_are_optional(self):
        c = self.config(); c.pop('patterns'); self.check_config(c, True)
    def test_unknown_pattern_rejected(self):
        c = self.config(); c['patterns'] = ['unknown']; self.check_config(c, False)
    def test_duplicate_pattern_rejected(self):
        c = self.config(); c['patterns'] = ['dto', 'dto']; self.check_config(c, False)
    def test_invalid_pattern_type_rejected(self):
        c = self.config(); c['patterns'] = 'dto'; self.check_config(c, False)
    def test_unknown_principle_rejected(self):
        c = self.config(); c['principles'] = ['unknown']; self.check_config(c, False)
    def test_known_pattern_catalog(self):
        c = self.config(); c['patterns'] = ['dto', 'repository', 'adapter', 'factory', 'strategy']; self.check_config(c, True)
    def test_unimplemented_exceptions_rejected(self):
        c = self.config(); c['governance']['exceptions'] = [{'path':'src/x'}]; self.check_config(c, False)

if __name__ == '__main__': unittest.main()
