#!/usr/bin/env bash
# Install ArchCore globally for Codex (including the VS Code extension).
# Symlinks point to this Git checkout; no project copies or marketplace required.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
BIN_HOME="${ARCHCORE_BIN_HOME:-$HOME/.local/bin}"
MODE="${1:-install}"
if [[ "$MODE" != install && "$MODE" != --check ]]; then
  echo "Usage: ./scripts/install.sh [--check]" >&2; exit 2
fi

links=(
  "$CODEX_HOME/skills/architecture-governance|$ROOT/skills/architecture-governance"
  "$CODEX_HOME/archcore|$ROOT/catalog"
  "$CODEX_HOME/agents/archcore-architect.toml|$ROOT/agents/archcore-architect.toml"
  "$CODEX_HOME/agents/archcore-guardian.toml|$ROOT/agents/archcore-guardian.toml"
  "$CODEX_HOME/agents/archcore-implementer.toml|$ROOT/agents/archcore-implementer.toml"
  "$CODEX_HOME/tools/archguard.py|$ROOT/tools/archguard.py"
  "$CODEX_HOME/tools/archcore_contract.py|$ROOT/tools/archcore_contract.py"
)

link_one() {
  local dest="$1" src="$2"
  if [[ ! -e "$src" ]]; then echo "Missing source: $src" >&2; return 1; fi
  if [[ -L "$dest" ]]; then
    if [[ "$(readlink "$dest")" == "$src" ]]; then echo "OK: $dest"; return 0; fi
    echo "CONFLICT: existing symlink $dest -> $(readlink "$dest")" >&2; return 1
  fi
  if [[ -e "$dest" ]]; then echo "CONFLICT: existing file/directory $dest (not overwritten)" >&2; return 1; fi
  if [[ "$MODE" == --check ]]; then echo "MISSING: $dest" >&2; return 1; fi
  mkdir -p -- "$(dirname "$dest")"
  ln -s -- "$src" "$dest"
  echo "Linked: $dest"
}

errors=0
for spec in "${links[@]}"; do
  dest="${spec%%|*}"; src="${spec#*|}"
  link_one "$dest" "$src" || errors=1
done

if ! python3 -c 'import yaml' >/dev/null 2>&1; then
  echo "WARNING: PyYAML missing. Install in the Python environment you use: python3 -m pip install PyYAML" >&2
  errors=1
else
  echo "OK: PyYAML available"
fi

if [[ "$MODE" == install ]]; then
  # Reuse existing safe, marked AGENTS.md registration without copying agent files.
  # The helper's instruction block is installed here using its existing markers.
  python3 - "$CODEX_HOME/AGENTS.md" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True)
start='<!-- ARCHCORE MANAGED START -->'; end='<!-- ARCHCORE MANAGED END -->'
block='\n'.join((start,
    'For repositories containing architecture.yaml, load the ArchCore architecture-governance skill and centrally installed catalog. For implementation requests, follow the skill\'s default Architect -> Guardian preflight -> Implementer -> Guardian post-review correction loop (up to three retries), using pytest for Python tests and ArchGuard for deterministic checks. For inspection-only requests do not edit. Never treat an agent recommendation as trusted human approval.',
    end))
old=p.read_text() if p.exists() else ''
if old.count(start)!=old.count(end) or old.count(start)>1:
    raise SystemExit('CONFLICT: malformed ArchCore markers in '+str(p)+'; no instructions modified')
if start in old:
    a=old.index(start); b=old.index(end)+len(end)
    new=old[:a]+block+old[b:]
else:
    new=old.rstrip()+('\n\n' if old.strip() else '')+block+'\n'
if new!=old:
    p.write_text(new)
    print('Updated managed instructions:',p)
else:
    print('OK: global instructions unchanged')
PY
else
  python3 - "$CODEX_HOME/AGENTS.md" <<'PY' || errors=1
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text() if p.exists() else ''
if '<!-- ARCHCORE MANAGED START -->' not in s or '<!-- ARCHCORE MANAGED END -->' not in s:
    print('MISSING: managed ArchCore global instructions'); sys.exit(1)
print('OK: ArchCore global instructions present')
PY
fi

# Optional launcher; it uses the repository's tools and can be invoked from any folder.
launcher="$BIN_HOME/archguard"
if [[ "$MODE" == install ]]; then
  if [[ ! -e "$launcher" && ! -L "$launcher" ]]; then
    mkdir -p "$BIN_HOME"
    cat > "$launcher" <<EOF2
#!/usr/bin/env bash
exec python3 "$ROOT/tools/archguard.py" "\$@" --catalog "$ROOT/catalog"
EOF2
    chmod +x "$launcher"
    echo "Created CLI launcher: $launcher"
  else
    echo "Existing launcher preserved: $launcher"
  fi
fi

if [[ ":$PATH:" != *":$BIN_HOME:"* ]]; then
  echo "NOTE: $BIN_HOME is not on PATH; use the full path to run archguard."
fi
if [[ "$errors" != 0 ]]; then
  echo "Installation/check incomplete; review conflicts or missing dependencies above." >&2
  exit 1
fi
echo "ArchCore ${MODE/install/installation} complete. Restart your Codex session in VS Code."
