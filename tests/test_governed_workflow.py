"""Governed workflow configuration checks (pytest)."""
from pathlib import Path
import os
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_skill_requires_both_reviews_and_bounded_rework():
    guidance = (ROOT / 'skills/architecture-governance/SKILL.md').read_text()
    for phrase in ('Guardian — preflight', 'Guardian — independent post-implementation review',
                   'three correction attempts', 'python3 -m pytest', 'actual changed files'):
        assert phrase in guidance
    assert 'trusted human approval' in guidance or 'trusted authorization' in guidance


@pytest.mark.parametrize('role,expected', [
    ('architect', 'Guardian preflight'),
    ('guardian', 'POST-IMPLEMENTATION'),
    ('implementer', 'Guardian issues REWORK'),
])
def test_agent_handoff_contract(role, expected):
    cfg = tomllib.loads((ROOT / f'agents/archcore-{role}.toml').read_text())
    assert expected in cfg['developer_instructions']


def test_install_updates_managed_instructions_idempotently(tmp_path):
    codex = tmp_path / 'codex'
    codex.mkdir()
    agents = codex / 'AGENTS.md'
    agents.write_text('Keep my unrelated global instructions.\n')
    env = {**os.environ, 'CODEX_HOME': str(codex), 'ARCHCORE_BIN_HOME': str(tmp_path / 'bin')}
    cmd = ['bash', str(ROOT / 'scripts/install.sh')]
    for _ in range(2):
        result = subprocess.run(cmd, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
    text = agents.read_text()
    assert 'Keep my unrelated global instructions.' in text
    assert text.count('<!-- ARCHCORE MANAGED START -->') == 1
    assert 'Guardian post-review correction loop' in text
    assert 'pytest' in text
    check = subprocess.run(cmd + ['--check'], env=env, capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr


def test_readme_has_git_native_installation_and_pytest():
    content = (ROOT / 'README.md').read_text()
    assert './scripts/install.sh' in content
    assert 'python3 -m pytest -q' in content
    assert 'Architect design' in content
    assert 'Guardian post-review' in content
