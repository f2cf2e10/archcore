from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / 'agents'

class AgentTests(unittest.TestCase):
    def test_three_roles_present_and_parseable(self):
        names = {'archcore-architect', 'archcore-guardian', 'archcore-implementer'}
        self.assertEqual({p.stem for p in AGENTS.glob('*.toml')}, names)
        for name in names:
            data = tomllib.loads((AGENTS / f'{name}.toml').read_text())
            self.assertEqual(data['name'], name)
            self.assertTrue(data['description'])
            self.assertIn('architecture.yaml', data['developer_instructions'])

