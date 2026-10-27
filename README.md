# ArchCore

ArchCore is a Git-managed architecture governance toolkit for Codex. A repository opts in by adding `architecture.yaml`; architectural knowledge, design guidance, agents, and scanning tools remain centrally maintained in this ArchCore repository.

ArchCore separates **architectures** (for example, Hexagonal), **methodologies** (DDD), **principles** (KISS, YAGNI, SOLID), **patterns** (DTO, Repository, Adapter), and **governance policies**. Selecting a pattern provides guidance; it does not require creating an abstraction.

## Repository layout

```text
archcore/
├── plugin.json                # Codex plugin manifest
├── .agents/plugins/marketplace.json  # Local repository marketplace
├── skills/                    # Reusable Codex skills
├── catalog/
│   ├── architectures/         # Hexagonal rules, explanation, illustration
│   ├── methodologies/
│   ├── principles/
│   └── patterns/
├── agents/                    # Optional standalone Codex subagents
├── tools/                     # Contract validator and read-only ArchGuard scanner
├── scripts/register_global.py # Optional global agent/instruction registration
├── examples/                  # Generic project contract
└── tests/
```

## Install for Codex in VS Code

Keep ArchCore in a stable Git checkout. Install once from the repository root:

```bash
./scripts/install.sh
```

The installer creates symbolic links from `~/.codex/` to this checkout for the architecture-governance skill, shared catalog, and Architect/Guardian/Implementer agents. It adds (or updates) a clearly marked ArchCore section in `~/.codex/AGENTS.md`, preserving unrelated instructions. It also provides `~/.local/bin/archguard` when that path is free. No marketplace registration, ZIP extraction instructions, or per-project copy of ArchCore is needed.

Verify the installation:

```bash
./scripts/install.sh --check
```

**Dependency:** The installer checks for PyYAML but deliberately does not modify your Python environment. If it reports that PyYAML is missing, install it in the Python environment used to run ArchGuard:

```bash
python3 -m pip install PyYAML
```

After installation, restart your Codex session in VS Code. Your application project opts in with its own `architecture.yaml` at the repository root; it does not need a project-specific `AGENTS.md`.

### Updating

Update this Git checkout normally:

```bash
git pull
./scripts/install.sh --check
```

Because Codex's files are symlinked to the checkout, knowledge definitions and agents update with Git. If you move the checkout, remove or adjust the old symlinks and rerun the installer. The script refuses to overwrite unrelated files, existing conflicting symlinks, or agent definitions.

The plugin manifest and optional marketplace metadata remain in the repository for clients that support plugins, but **the VS Code installation above does not depend on marketplace support**.

## Using ArchCore in a project

Add **only** an `architecture.yaml` file to the project root (see `examples/generic-hexagonal/architecture.yaml`). A project-level `AGENTS.md` is optional; architecture selection does not require one.

Ask Codex:

> Use ArchCore to inspect this repository. Read `architecture.yaml`, validate it, run the read-only ArchGuard scan, and report structural and dependency violations. Do not modify files.

Or run the tools directly from the ArchCore checkout:

```bash
# From the ArchCore checkout, change --project to your target repository
python3 tools/archcore_contract.py validate /path/to/project/architecture.yaml --catalog ./catalog
python3 tools/archguard.py scan --project /path/to/project --catalog ./catalog --format json
python3 tools/archguard.py check --project /path/to/project --catalog ./catalog
python3 tools/archguard.py scan --project /path/to/project --catalog ./catalog --format dot --graph-level files > graph.dot
```

To update the repository and run tests:

```bash
cd ~/src/archcore
git pull
python3 -m pytest -q
```

If the plugin client caches marketplace installations, refresh/reinstall the plugin through that client after updating the checkout. The optional standalone agents may also need re-registration.

## Default governed implementation in VS Code

After installing from this Git checkout using `./scripts/install.sh`, restart the Codex session. With `architecture.yaml` in the target project root, give Codex a normal implementation request:

> Implement the requested feature following ArchCore governance. Add pytest coverage and run ArchGuard.

The global instructions activate the `architecture-governance` skill. For nontrivial work, the expected sequence is **Architect design → Guardian preflight → Implementer edits/tests → Guardian post-review**. Failed review returns concrete issues to the Implementer for correction and repeat review, up to three attempts. A design failure returns to Architect; protected modifications stop for trusted external authorization. The Guardian reviews the actual diff, not just the design. On clients without active subagent delegation, the sequence is performed in one thread and is **not** an independent review.

For a report without modifications:

> Use ArchCore to scan and review this repository. Do not modify any files.

Run project tests with `python3 -m pytest -q`. ArchCore also runs its own test suite using pytest:

```bash
python3 -m pip install PyYAML pytest
python3 -m pytest -q
./scripts/install.sh --check
```

Pytest and ArchGuard produce evidence, not trusted approval. A Guardian `PASS` is an advisory compliance verdict; server-side enforcement is a separate phase.

## Current capabilities and limits

- Validates contract selections and configuration using the supported catalog.
- Scans filesystem layout, classifies configured layers, builds a static Python import dependency graph, and reports detected dependency and structural violations.
- Produces readable, JSON, and DOT graph output.
- Does **not** yet guarantee complete dependency coverage, prove semantic design quality, enforce trusted approval, or prevent an agent from editing protected paths. Dynamic imports and runtime dependency wiring may escape static analysis.
- Agent recommendations are **not** trusted human approvals; deterministic enforcement and CI integration remain separate work.

## Development

```bash
python3 -m pytest -q
```

Changes to knowledge modules, manifests, and documentation are committed to this Git repository. Do not add naming suffixes to architecture or methodology identifiers; Git history records changes. The portable plugin manifest contains package metadata required by its format, independent of internal module naming.

## Phase 4 — ArchGuard deterministic checks

```bash
archguard scan --project . --format json
archguard scan --project . --format dot --graph-level files > graph.dot
archguard check --project .
archguard check --project . --changed
archguard check --project . --changed --base origin/main
archguard check --project . --changed --scope src/my_package/infrastructure
archguard explain
```

ArchGuard checks declared directories, concrete Python import dependencies (including detected transitive chains), centrally configured forbidden framework imports, explicit `ports/` and `adapters/` directory placement, and Git-modified paths when `--changed` is supplied. It reports dynamic imports as warnings. Output is read-only and supports machine-consumable JSON and DOT. The `--changed` option requires the selected project directory to be the Git root; it includes unstaged, staged and untracked files, as well as optional differences from `--base`. Protected and unclassified changes **fail closed**: approval enforcement remains Phase 5. Directory names are only proxies for port/adapter placement, not proof of implementation correctness.

Static analysis does not guarantee Python runtime import resolution, detect all reflection, or prove domain purity and correct business-rule placement. This tool is not a security boundary by itself; CI and branch restrictions are needed for trusted enforcement.
